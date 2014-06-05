__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

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
    
class Executer(ThreadEx):
    jobs = {}
    self.jobs_lock = threading.RLock()
    
    def __init__(self, store):
        ThreadEx.__init__(self)
        self.exec_process = None
        self.process_lock = threading.RLock()
        self.store = store
        self.globals = globals.Globals()
        
    def add_job(self, job):
        self.jobs_lock.acquire()
        self.jobs['%d' % t] = job.start()
        self.write(job)
        self.jobs_lock.release()
        
    def update_job(self, timestamp, data):
        self.jobs_lock.acquire()
        self.jobs['%d' % timestamp].update(data)
        self.jobs_lock.release()

    def finish_jobs(self, activities = []):
        finished_jobs = []
        self.jobs_lock.acquire()
        t = int(time.time() * 1000)

        for job_timestamp in self.jobs.keys():
            job = self.jobs[job_timestamp]
            
            if job.details['_id'] in activities:
                job.stop() and _log.info('Killed activity (%s @ %d)' % (job.details['_id'], job.timestamp))
                job.close_file()
            elif t - job.timestamp > self.timeout:
                job.stop() and _log.info('Killed activity (%s @ %d) as it exceeded timeout' % (job.details['_id'], job.timestamp))

            if job.get_status() != JobStatus.RUNNING:
                finished_jobs.append(job)
                del self.jobs[job_timestamp]

        self.jobs_lock.release()
        return finished_jobs
        
    def exe(self):
        while 1:
            try:
                self.read()
            finally:
                if self.globals.stop_event.is_set():
                    break
                    
        self.process.terminate()
        
    @property
    def process(self):
        self.process_lock.acquire()
        
        if self.exec_process == None or self.exec_process.poll() != None:
            self.exec_process and os.waitpid(-1 * self.exec_process.pid, os.WUNTRACED)
            self.exec_process = subprocess.Popen([globals.Globals().exe_path + 'bin/execute.sh'], stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        
        self.process_lock.release()
        return self.exec_process
    
    def write(self, job):
        self.process.stdin.write('%d %s: %s\n' % (job.exec_details['timestamp'], job.exec_details['output_file'].name, job.exec_details['command']))
        
    def read(self):
        data = self.process.stdout.readline().split()
        self.update_job(data[0], {data[1]: data[2]})
        

class Job:    
    def __init__(self, activity, store):
        self.is_whitelisted = activity['is_whitelisted']
        self.exec_timestamp = activity['next_exec_timestamp']
        self.status = JobStatus.NOT_RUNNING
        self.exec_details = {
            'timestamp': 0,
            'output_file': None,
            'pid': -1,
            'return_code': 0
        }
        self.exec_details.update(dict([detail for detail in activity['details'] if detail[0] in ['_id', 'command']]))
        self.store = store

    def start(self):
        t = int(time.time() * 1000)
        self.exec_details['timestamp'] = t

        if self.is_whitelisted == True:
            _log.debug('Executing activity(%s @ %d)' % (self.exec_details['_id'], t))
            self.exec_details['output_file'] = tempfile.NamedTemporaryFile(dir = self.globals.temp_path)
            self.status = JobStatus.RUNNING
        else:
            _log.info('Activity %s is blocked by whitelist' % self.details['_id'])

        return t

    def stop(self):
        try:
            os.kill(self.exec_details['pid'], signal.SIGTERM)
            self.status = JobStatus.TIMED_OUT
            return True
        except:
            return False
        
    def update(self, data):
        self.exec_details.update(data)
        
        if 'return_code' in data:
            self.status = JobStatus.NOT_RUNNING

    def post_output(self):
        data = None

        if self.exec_details['pid'] == None:
            data = {'timestamp': self.exec_details['timestamp'], 'returnCode': 0, 'data': 'Command blocked by whitelist.'}
        elif self.status == JobStatus.TIMED_OUT:
            data = {'timestamp': self.exec_details['timestamp'], 'returnCode': 0, 'data': 'Command exceeded timeout.'}
        elif self.exec_details['output_file']:
            self.exec_details['output_file'].seek(0, os.SEEK_SET)
            data = {
                'timestamp': self.exec_details['timestamp'], 
                'returnCode': self.exec_details['return_code'], 
                'data': self.exec_details['output_file'].read(256 * 1024)
            }

            if not data['data']:
                data['data'] = 'No output produced'
                _log.debug('No output/error found for activity (%s @ %d)' % (self.exec_details['_id'], self.exec_details['timestamp']))

        self.close_file()

        if data:
            _log.debug('Pushing activity (%s @ %d) to %s' % (self.details['_id'], self.timestamp, self.store.__class__.__name__))
            self.store.push(self.details['_id'], data)

    def close_file(self):
        self.exec_details['output_file'] and self.exec_details['output_file'].close()
        self.exec_details['output_file'] = None

        
class JobProducer(SingletonType('JobProducerMetaClass', (ThreadEx, ), {})):
    def __init__(self, store):
        ThreadEx.__init__(self)
        self.prev_time = time.time()
        self.globals = globals.Globals()
        self.activities_lock = threading.RLock()
        self.activities = {}
        self.queue = queue.Queue()
        self.sleep_interval = 5
        self.store = store
        self.consumer_count = 0
        self.executer = Executer(store)

        try:
            self.timeout = self.globals.config.sealion.commandTimeout
        except:
            self.timeout = 30

        self.timeout = int(self.timeout * 1000)
        self.globals.event_dispatcher.bind('get_activity_funct', self.get_activity_funct)

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

    def schedule_activities(self):
        self.activities_lock.acquire()
        t, jobs = time.time(), []

        for activity_id in self.activities:
            activity = self.activities[activity_id]
            next_exec_timestamp = activity['next_exec_timestamp']

            if next_exec_timestamp <= t + self.sleep_interval:                
                jobs.append(Job(activity, self.store))
                activity['next_exec_timestamp'] = next_exec_timestamp + activity['details']['interval']

        jobs.sort(key = lambda job: job.exec_timestamp)
        len(jobs) and _log.debug('Scheduling %d activities', len(jobs))

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
        self.executer.start()
        self.set_activities();
        self.globals.event_dispatcher.bind('set_activities', self.set_activities)
        
        while 1:
            self.schedule_activities()
            self.globals.stop_event.wait(self.sleep_interval)

            if self.globals.stop_event.is_set():
                _log.debug('%s received stop event' % self.name)
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
            
    def get_activity_funct(self, event, callback):
        callback(self.get_activity)
                
    def get_activity(self, activity):
        self.activities_lock.acquire()
        
        try:      
            return self.activities.get(activity)
        finally:
            self.activities_lock.release()

class JobConsumer(ThreadEx):
    unique_id = 1
    
    def __init__(self):
        ThreadEx.__init__(self)
        self.job_producer = JobProducer()
        self.globals = globals.Globals()
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
            self.job_producer.executer.add_job(job)
