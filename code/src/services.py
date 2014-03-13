import logging
import threading
import time
import subprocess
import re
import signal
import os
import tempfile
import globals
from constructs import *

_log = logging.getLogger(__name__)

class JobStatus(Namespace):
    NOT_RUNNING = 0
    RUNNING = 1
    TIMED_OUT = 2

class Job:
    timestamp_lock = threading.RLock()
    
    def __init__(self, activity, store):
        self.activity = activity
        self.status = JobStatus.NOT_RUNNING
        self.timestamp = 0
        self.process = None
        self.output_file = None
        self.exec_timestamp = activity['next_exec_timestamp']
        self.details = self.activity['details']
        self.store = store

    def start(self):
        self.timestamp = int(time.time() * 1000)

        if self.activity['is_whitelisted'] == True:
            _log.debug('Executing activity(%s @ %d)' % (self.details['_id'], self.timestamp))
            self.output_file = tempfile.TemporaryFile()
            self.process = subprocess.Popen(self.details['command'], shell=True, stdout = self.output_file, stderr = self.output_file, preexec_fn = os.setpgrp)
            self.status = JobStatus.RUNNING
        else:
            _log.info('Activity %s is blocked by whitelist.' % self.details['_id'])

        return self

    def stop(self):
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
            os.waitpid(-1 * self.process.pid, os.WUNTRACED)
            self.status = JobStatus.TIMED_OUT
            self.process.returncode = 0
            return True
        except:
            return False

    def get_status(self):
        if self.status == JobStatus.RUNNING and self.process.poll() != None:
            self.status = JobStatus.NOT_RUNNING

            try:
                os.waitpid(-1 * self.process.pid, os.WUNTRACED)
            except:
                pass

        return self.status

    def post_output(self):
        data = None

        if self.process == None:
            data = {'timestamp': self.timestamp, 'returnCode': 0, 'data': 'Command blocked by whitelist.'}
        elif self.get_status() == JobStatus.TIMED_OUT:
            data = {'timestamp': self.timestamp, 'returnCode': 0, 'data': 'Command exceeded timeout.'}
        elif self.output_file:
            self.output_file.seek(0, os.SEEK_SET)
            data = {'timestamp': self.timestamp, 'returnCode': self.process.returncode, 'data': self.output_file.read(256 * 1024)}

            if not data['data']:
                data['data'] = 'No output produced'
                _log.debug('No output/error found for activity (%s @ %d)' % (self.details['_id'], self.timestamp))

        self.close_file()

        if data:
            _log.debug('Pushing activity (%s @ %d) to %s' % (self.details['_id'], self.timestamp, self.store.__class__.__name__))
            self.store.push(self.details['_id'], data)

    def close_file(self):
        self.output_file and self.output_file.close()
        self.output_file = None

        
class JobProducer(SingletonType('JobProducerMetaClass', (ThreadEx, ), {})):
    def __init__(self, store):
        ThreadEx.__init__(self)
        self.prev_time = time.time()
        self.globals = globals.Interface()
        self.jobs = []
        self.jobs_lock = threading.RLock()
        self.activities_lock = threading.Lock()
        self.activities = {}
        self.queue = queue.Queue()
        self.sleep_interval = 5
        self.store = store
        self.consumer_count = 0

        try:
            self.timeout = self.globals.config.sealion.commandTimeout
        except:
            self.timeout = 30

        self.timeout = int(self.timeout * 1000)
        self.globals.event_dispatcher.bind('get_activity', self.get_activity)

    def is_in_whitelist(self, command):
        whitelist = []
        is_whitelisted = True

        if hasattr(self.globals.config.sealion, 'whitelist'):
            whitelist = self.globals.config.sealion.whitelist

        if len(whitelist):
            is_whitelisted = False

            for i in range(0, len(whitelist)):
                if re.match(whitelist[i], command):
                    is_whitelisted = True
                    break

        return is_whitelisted
    
    def add_job(self, job):
        self.jobs_lock.acquire()
        t = time.time()
        
        if t - self.prev_time < 0.250:
            time.sleep(0.250 - (t - self.prev_time))
            
        self.prev_time = t
        self.jobs.append(job.start())
        self.jobs_lock.release()

    def finish_jobs(self, activities = []):
        finished_jobs = []
        running_jobs = []
        self.jobs_lock.acquire()
        t = int(time.time() * 1000)

        for job in self.jobs:
            if activities == None or (job.details['_id'] in activities):
                job.stop() and _log.info('Killed activity (%s @ %d)' % (job.details['_id'], job.timestamp))
                job.close_file()
            elif t - job.timestamp > self.timeout:
                job.stop() and _log.info('Killed activity (%s @ %d) as it exceeded timeout' % (job.details['_id'], job.timestamp))

            if job.get_status() != JobStatus.RUNNING:
                finished_jobs.append(job)
            else:
                running_jobs.append(job)

        self.jobs = running_jobs
        self.jobs_lock.release()
        return finished_jobs

    def schedule_activities(self):
        self.activities_lock.acquire()
        t, jobs = time.time(), []

        for activity_id in self.activities:
            activity = self.activities[activity_id]
            next_exec_timestamp = activity['next_exec_timestamp']

            if next_exec_timestamp <= t + self.sleep_interval:                
                jobs.append(Job(activity, self.store))
                activity['next_exec_timestamp'] = next_exec_timestamp + activity['details']['interval']

        jobs = sorted(jobs, key = lambda job: job.exec_timestamp)
        len(jobs) and _log.info('Scheduling %d activities', len(jobs))

        for job in jobs:
            self.queue.put(job)

        self.activities_lock.release()
        
    def set_activities(self, event = None):
        activities = self.globals.config.agent.activities
        start_count, update_count, stop_count, activity_ids = 0, 0, 0, []
        self.activities_lock.acquire()        
        t = time.time()
        
        for activity in activities:
            activity_id = activity['_id']
            cur_activity = self.activities.get(activity_id)
            
            if cur_activity:
                details = cur_activity['details']
                
                if details['interval'] != activity['interval'] or details['command'] != activity['command']:
                    cur_activity['details'] = activity
                    cur_activity['is_whitelisted'] = self.is_in_whitelist(activity['command'])
                    cur_activity['next_exec_timestamp'] = t
                    _log.info('Updating activity %s' % activity_id)
                    update_count += 1
                    t += 0.250
            else:
                self.activities[activity_id] = {
                    'details': activity,
                    'is_whitelisted': self.is_in_whitelist(activity['command']),
                    'next_exec_timestamp': t
                }
                _log.info('Starting activity %s' % activity_id)
                start_count += 1
                t += 0.250
                
            activity_ids.append(activity_id)
            
        deleted_activity_ids = [activity_id for activity_id in self.activities if (activity_id in activity_ids) == False]
        
        for activity_id in deleted_activity_ids:
            _log.info('Stopping activity %s' % activity_id)
            del self.activities[activity_id]
            stop_count += 1
            
        self.store.clear_offline_data(activity_ids)
        self.activities_lock.release()
        self.start_consumers(len(activity_ids))    
        self.stop_consumers(len(activity_ids))
        
        if start_count + update_count > 0:
            self.schedule_activities()
        
        _log.info('%d started; %d updated; %d stopped' % (start_count, update_count, stop_count))
        
    def exe(self):        
        self.set_activities();
        self.globals.event_dispatcher.bind('set_activities', self.set_activities)
        
        while 1:
            self.schedule_activities()
            self.globals.stop_event.wait(self.sleep_interval)

            if self.globals.stop_event.is_set():
                _log.debug('%s received stop event.' % self.name)
                break

        self.stop_consumers()
        
    def start_consumers(self, count = 16):
        count = min(16, count)
        count - self.consumer_count > 0 and _log.info('Starting %d job consumers' % (count - self.consumer_count))
        
        while self.consumer_count < count:
            self.consumer_count += 1
            JobConsumer().start()

    def stop_consumers(self, count = 0):
        self.consumer_count - count > 0 and _log.info('Stopping %d job consumers' % (self.consumer_count - count))
        
        while self.consumer_count > count:
            self.queue.put(None)
            self.consumer_count -= 1
                
    def get_activity(self, event, activity, callback):
        self.activities_lock.acquire()
        ret = self.activities.get(activity)
        self.activities_lock.release()
        callback(ret)

class JobConsumer(ThreadEx):
    unique_id = 1
    
    def __init__(self):
        ThreadEx.__init__(self)
        self.job_producer = JobProducer()
        self.globals = globals.Interface()
        self.name = '%s-%d' % (self.__class__.__name__, JobConsumer.unique_id)
        JobConsumer.unique_id += 1

    def exe(self):       
        while 1:
            job = self.job_producer.queue.get()

            if self.globals.stop_event.is_set() or job == None:
                _log.debug('%s received stop event' % self.name)
                break

            t = time.time()
            job.exec_timestamp - t > 0 and time.sleep(job.exec_timestamp - t)
            self.job_producer.add_job(job)
