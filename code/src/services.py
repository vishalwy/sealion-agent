import logging
import threading
import time
import subprocess
import re
import signal
import os
from constructs import *
from globals import Globals
import connection

_log = logging.getLogger(__name__)

class Job:
    timestamp_lock = threading.RLock()
    prev_time = int(time.time() * 1000)
    
    def __init__(self, activity_id, command):
        self.activity_id = activity_id
        self.command = command
        self.timestamp = Job.get_timestamp()
        self.is_timedout = False
        self.process = None
    
    @staticmethod
    def get_timestamp():
        Job.timestamp_lock.acquire()
        t = int(time.time() * 1000)
        
        if t - Job.prev_time < 200:
            time.sleep(0.200)
            
        Job.prev_time = t
        Job.timestamp_lock.release()
        return t
    
    def start(self):
        self.process = subprocess.Popen(['sh', '-c', self.command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
    def stop(self):
        try:
            os.kill(self.process.pid, signal.SIGKILL)
            os.waitpid(-1, os.WNOHANG)
            self.is_timedout = True
            self.process.returncode = 0
            return True
        except:
            return False
        
    def send(self):
        data = {'returnCode': 0, 'timestamp': self.timestamp}
        
        if self.process == None:
            data['data'] = 'Command blocked by whitelist.'
        elif self.is_timedout == True:
            data['data'] = 'Command exceeded timeout.'
        else:            
            output = self.process.stdout.read(256 * 1024)
            data['data'] = output if output else self.process.stderr.read()
            data['returnCode'] = self.process.returncode
            
        _log.debug('Pushing activity(%s @ %d) to store' % (self.activity_id, self.timestamp))
        Globals().store.push(self.activity_id, data)
        

class Activity(ThreadEx):
    jobs_lock = threading.RLock()
    jobs = []
    timeout = -1
    
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
    def reset_timeout():
        _log.debug('Resetting activity timeout to -1')
        Activity.timeout = -1
    
    @staticmethod
    def put_job(job):
        Activity.jobs_lock.acquire()
        Activity.jobs.append(job)
        Activity.jobs_lock.release()
        
    @staticmethod
    def get_finished_jobs():
        t = int(time.time() * 1000)
        finished_jobs = []
        running_jobs = []
        Activity.jobs_lock.acquire()
        
        for job in Activity.jobs:
            if t - job.timestamp > Activity.timeout:
                job.stop() and _log.info('Killed activity(%s @ %d) as it exceeded timeout' % (job.activity_id, job.timestamp))
                
            if job.process.poll() != None:
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
            self.execute()
            timeout = self.activity['interval']
            break_flag = False
            
            while timeout > 0:
                if self.globals.stop_event.is_set() or self.is_stop == True:
                    _log.debug('Activity %s received stop event' % self.activity['_id'])
                    break_flag = True
                    break
                
                time.sleep(min(5, timeout))
                timeout -= 5
                
            if break_flag == True:
                break

        _log.info('Shutting down activity %s' % self.activity['_id'])
        
    def execute(self):
        job = Job(self.activity['_id'], self.activity['command'])
        
        if self.is_whitelisted == False:
            _log.info('Activity ' + job.activity_id + ' is blocked by whitelist')
            job.send()
        else:
            job.start()
            Activity.put_job(job)
        
    def stop(self):
        self.is_stop = True       
       
class Controller(ThreadEx):
    __metaclass__ = SingletonType
    
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
                    self.globals.api.update_agent(self.globals.exe_path)
                
                _log.debug('Controller waiting for stop event for %d seconds' % (5 * 60, ))
                self.globals.stop_event.wait(5 * 60)
                
                if self.globals.stop_event.is_set():
                    _log.debug('Controller received stop event')
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
                    for job in Activity.get_finished_jobs():
                        job.send()
                        
                    self.globals.stop_event.wait(5)
                    
                    if self.globals.stop_event.is_set():
                        _log.debug('Controller received stop event')
                        Activity.reset_timeout()
                        Activity.get_finished_jobs()
                        break
                
                self.stop_threads()
            
                if self.handle_response(self.globals.api.stop_status) == False:
                    break

                if self.is_stop == True:
                    break

                self.globals.reset_interfaces()
        
        self.is_stop = True
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
        threads = threading.enumerate()
        curr_thread = threading.current_thread()

        for thread in threads:
            if thread.ident != curr_thread.ident and thread.ident != self.main_thread.ident:
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
    
def quit(status = 0):
    _log.info('Agent shutting down with status code %d' % status)
    exit(status)
    
def start():
    _log.info('Agent starting up')
    
    globals = Globals()
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
            globals.api.logout()
            quit()

