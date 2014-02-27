import logging
import threading
import time
import subprocess
import re
import signal
import os
import sys
import tempfile
from datetime import datetime
from constructs import *
from globals import Globals
import connection

_log = logging.getLogger(__name__)
_metric = {'starting_time': 0, 'stopping_time': 0}

class JobStatus(Namespace):
    NOT_RUNNING = 0
    RUNNING = 1
    TIMED_OUT = 2

class Job:    
    def __init__(self, activity, is_whitelisted):
        self.activity = activity
        self.is_whitelisted = is_whitelisted
        self.status = JobStatus.NOT_RUNNING
        self.timestamp = 0
        self.process = None
        self.output_file = None
    
    def start(self):
        self.timestamp = int(time.time() * 1000)
        
        if self.is_whitelisted == True:
            _log.debug('Executing activity(%s @ %d)' % (self.activity['_id'], self.timestamp))
            self.output_file = tempfile.TemporaryFile()
            self.process = subprocess.Popen(self.activity['command'], shell=True, stdout = self.output_file, stderr = self.output_file, preexec_fn = os.setpgrp)
            self.status = JobStatus.RUNNING
        else:
            _log.info('Activity %s is blocked by whitelist' % self.activity['_id'])
            
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
                _log.debug('No output/error found for activity(%s @ %d)' % (self.activity['_id'], self.timestamp))
            
        self.close_file()
        
        if data:
            _log.debug('Pushing activity(%s @ %d) to store' % (self.activity['_id'], self.timestamp))
            Globals().store.push(self.activity['_id'], data)
        
    def close_file(self):
        self.output_file and self.output_file.close()
        self.output_file = None

class Activity(ThreadEx):
    jobs = []
    timeout = -1
    jobs_lock = threading.RLock()
    prev_time = int(time.time() * 1000)
    
    def __init__(self, activity):
        ThreadEx.__init__(self)
        self.activity = activity;
        self.is_stop = False
        self.globals = Globals()
        self.is_whitelisted = self.is_in_whitelist()
        
        if Activity.timeout == -1:
            try:
                Activity.timeout = self.globals.config.sealion.commandTimeout
            except:
                Activity.timeout = 30
                
            Activity.timeout = int(Activity.timeout * 1000)
    
    @staticmethod
    def add_job(job):
        Activity.jobs_lock.acquire()
        t = int(time.time() * 1000)
        
        if t - Activity.prev_time < 250:
            time.sleep(0.250)
            
        Activity.prev_time = t
        Activity.jobs.append(job.start())
        Activity.jobs_lock.release()
        
    @staticmethod
    def finish_jobs(activities = []):
        finished_jobs = []
        running_jobs = []
        Activity.jobs_lock.acquire()
        t = int(time.time() * 1000)
        
        for job in Activity.jobs:
            if activities == None or (job.activity['_id'] in activities):
                job.stop() and _log.info('Killed activity(%s @ %d)' % (job.activity['_id'], job.timestamp))
                job.close_file()
            elif t - job.timestamp > Activity.timeout:
                job.stop() and _log.info('Killed activity(%s @ %d) as it exceeded timeout' % (job.activity['_id'], job.timestamp))
            
            if job.get_status() != JobStatus.RUNNING:
                finished_jobs.append(job)
            else:
                running_jobs.append(job)
        
        Activity.jobs = running_jobs
        Activity.jobs_lock.release()
        return finished_jobs
        
    def is_in_whitelist(self):
        whitelist = []
        is_whitelisted = True
        command = self.activity['command']

        if hasattr(self.globals.config.sealion, 'whitelist'):
            whitelist = self.globals.config.sealion.whitelist

        if len(whitelist):
            is_whitelisted = False

            for i in range(0, len(whitelist)):
                if re.match(whitelist[i], command):
                    is_whitelisted = True
                    break
                    
        return is_whitelisted

    def exe(self):
        _log.info('Starting up activity %s' % self.activity['_id'])                      
        
        while 1:
            Activity.add_job(Job(self.activity, self.is_whitelisted))
            timeout = self.activity['interval']
            break_flag = False
            
            while timeout > 0:
                if self.globals.stop_event.is_set() or self.is_stop == True:
                    _log.debug('Activity %s received stop event' % self.activity['_id'])
                    break_flag = True
                    break
                
                time.sleep(min(2, timeout))
                timeout -= 2
                
            if break_flag == True:
                break

        self.is_stop and Activity.finish_jobs([self.activity['_id']])
        _log.info('Shutting down activity %s' % self.activity['_id'])
        
    def stop(self):
        self.is_stop = True       

class Controller(SingletonType('ControllerMetaClass', (object, ), {}), ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = Globals()
        self.is_stop = False
        self.main_thread = threading.current_thread()
    
    def handle_response(self, status):
        _log.debug('Handling response status %d' % status)
        
        if status == self.globals.APIStatus.SUCCESS:
            return True
        elif self.globals.api.is_not_connected(status):
            _log.info('Failed to connect')
        elif status == self.globals.APIStatus.NOT_FOUND:           
            try:
                _log.info('Uninstalling agent')
                subprocess.Popen([self.globals.exe_path + 'uninstall.sh'])
            except:
                _log.error('Failed to open uninstall script')
                
        elif status == self.globals.APIStatus.UNAUTHERIZED:
            _log.error('Agent unautherized to connect')
        elif status == self.globals.APIStatus.BAD_REQUEST:
            _log.error('Server marked the request as bad')
        elif status == self.globals.APIStatus.SESSION_CONFLICT:
            _log.error('Agent session conflict')

        return False
        
    def exe(self):
        _log.debug('Controller starting up')
        
        while 1:
            if self.globals.is_update_only_mode == True:
                version = self.globals.api.get_agent_version()
                version_type = type(version)

                if (version_type is str or version_type is unicode) and version != self.globals.config.agent.agentVersion:
                    self.globals.api.update_agent()

                _log.debug('Controller waiting for stop event for %d seconds' % (5 * 60, ))
                self.globals.stop_event.wait(5 * 60)

                if self.globals.stop_event.is_set():
                    _log.debug('Controller received stop event')
                    _metric['stopping_time'] = time.time()
                    break
            else:
                if self.handle_response(connection.Interface(self.globals).connect()) == False:
                    break

                if self.globals.store.start() == False:
                    break

                if len(self.globals.config.agent.activities) == 0:
                    self.globals.store.clear_offline_data()

                self.globals.manage_activities();

                while 1:             
                    finished_job_count = 0

                    for job in Activity.finish_jobs():
                        job.post_output()
                        finished_job_count += 1

                    finished_job_count and _log.debug('Fetched %d finished jobs', finished_job_count)
                    self.globals.stop_event.wait(5)

                    if self.globals.stop_event.is_set():
                        _log.debug('Controller received stop event')
                        _metric['stopping_time'] = time.time()
                        Activity.finish_jobs(None)
                        break
                        
                break

        self.is_stop = True
        self.stop_threads()

        _log.debug('Controller generating SIGALRM signal')
        signal.alarm(1)
        _log.debug('Controller shutting down')
            
    def stop(self):
        self.is_stop = True
        self.globals.api.stop()
        
    def stop_threads(self):
        _log.debug('Stopping all threads')
        self.globals.api.stop()
        self.globals.rtc.stop()
        self.globals.api.logout()
        self.globals.api.close()
        threads = threading.enumerate()
        curr_thread = threading.current_thread()

        for thread in threads:
            if thread.ident != curr_thread.ident and thread.ident != self.main_thread.ident and thread.daemon != True:
                _log.debug('Waiting for ' + str(thread))
                thread.join()

def sig_handler(signum, frame):    
    if signum == signal.SIGTERM:
        _log.info('Received SIGTERM signal')
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        Controller().stop()
    elif signum == signal.SIGINT:
        _log.info('Received SIGINT signal')
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        Controller().stop()
    elif signum == signal.SIGALRM:
        _log.debug('Received SIGALRM signal')
        signal.alarm(0)
        
def stop(status = 0):
    _log.info('Agent shutting down with status code %d' % status)
    _log.debug('Took %f seconds to shutdown' % (time.time() - _metric['stopping_time']))
    _log.info('Ran for %s hours' % str(datetime.now() - datetime.fromtimestamp(_metric['starting_time'])))
    exit(status)
    
def start():
    _metric['starting_time'] = time.time()
    _log.info('Agent starting up')
    _log.info('Using python binary at %s' % sys.executable)
    _log.info('Python version : %s' % '.'.join([str(i) for i in sys.version_info]))
    globals = Globals()
    _log.info('Agent version  : %s' % globals.config.agent.agentVersion)
    globals.activity_type = Activity
    controller = Controller()
    signal.signal(signal.SIGALRM, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    controller.start()
    
    while 1:
        _log.debug('Waiting for signals SIGALRM or SIGTERM or SIGINT')
        signal.pause()
        
        if controller.is_stop == True:
            controller.join()
            break

    stop()

