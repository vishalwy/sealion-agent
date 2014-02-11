import logging
import threading
import time
import subprocess
import re
import signal
import os
from constructs import *
from globals import Globals

_log = logging.getLogger(__name__)

class Activity(ExceptionThread):
    timestampLock = threading.RLock()
    
    def __init__(self, activity, stop_event):
        ExceptionThread.__init__(self)
        self.activity = activity;
        self.stop_event = stop_event
        self.is_stop = False
        self.is_whitelisted = self.is_in_whitelist()
        
    @staticmethod
    def get_timestamp():
        Activity.timestampLock.acquire()
        t = int(time.time() * 1000)
        time.sleep(0.001)
        Activity.timestampLock.release()
        return t
        
    def is_in_whitelist(self):
        globals = Globals()
        whitelist = []
        is_whitelisted = True
        command = self.activity['command']

        if hasattr(globals.config.sealion, 'whitelist'):
            whitelist = globals.config.sealion.whitelist

        if len(whitelist):
            is_whitelisted = False

            for i in range(0, len(whitelist)):
                if re.match(whitelist[i], command):
                    is_whitelisted = True
                    break
                    
        return is_whitelisted

    def exe(self):
        _log.info('Starting up activity %s' % self.activity['_id'])
        globals = Globals()
        self.timeout = 30
        
        if hasattr(globals.config.sealion, 'commandTimeout'):
            self.timeout = globals.config.sealion.commandTimeout            
        
        while 1:                
            timestamp = Activity.get_timestamp()
            ret = self.execute()      
            
            if ret != None:
                data = {'returnCode': ret['return_code'], 'timestamp': timestamp, 'data': ret['output']}
                _log.debug('Pushing activity(%s @ %d) to store' % (self.activity['_id'], timestamp))
                globals.store.push(self.activity['_id'], data)
                
            timeout = self.activity['interval']
            break_flag = False
            
            while timeout > 0:
                if self.stop_event.is_set() or self.is_stop == True:
                    _log.debug('Activity %s received stop event' % self.activity['_id'])
                    break_flag = True
                    break
                
                time.sleep(min(5, timeout))
                timeout -= 5
                
            if break_flag == True:
                break

        _log.info('Shutting down activity %s' % self.activity['_id'])

    def execute(self):
        if self.is_whitelisted == False:
            ret = {'return_code': 0, 'output': 'Command blocked by whitelist.'}
            _log.info('Command ' + self.activity['_id'] + ' is blocked by whitelist')
            return ret
        
        ret = {'output': 'Command exceded timeout', 'return_code': 0};
        p = subprocess.Popen(['sh', '-c', self.activity['command']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        start_time = time.time()
        
        while p.poll() is None:
            time.sleep(1)
            
            if self.stop_event.is_set() or self.is_stop == True:
                return None
            
            if time.time() - start_time > self.timeout:
                _log.info('Command ' + self.activity['_id'] + ' exceded timeout; killing now')
                os.kill(p.pid, signal.SIGKILL)
                os.waitpid(-1, os.WNOHANG)
                return ret
            
        output = p.stdout.read(256 * 1024)
        ret['output'] = output if output else p.stderr.read()
        ret['return_code'] = p.returncode;
        return ret
        
    def stop(self):
        self.is_stop = True
    
class Connection(ExceptionThread):    
    def exe(self):
        _log.debug('Starting up connection')
        self.attempt(retry_interval = 20)
        _log.debug('Shutting down connection')
    
    def attempt(self, max_try = -1, retry_interval = 5):
        globals = Globals()
        status = globals.api.authenticate(max_try, retry_interval)
        
        if status == globals.APIStatus.SUCCESS and globals.is_update_only_mode == False: 
            globals.rtc.connect().start()
            
        return status            
        
    def connect(self):
        globals = Globals()
        status = globals.APIStatus.SUCCESS
        
        if hasattr(globals.config.agent, '_id') == False:
            status = globals.api.register(retry_count = 4, retry_interval = 10)
            
        if status != globals.APIStatus.SUCCESS:
            return status
        
        status = self.attempt(2)
        
        if globals.api.is_not_connected(status):
            if globals.is_update_only_mode == True:
                self.start()
                status = globals.APIStatus.SUCCESS
            elif hasattr(globals.config.agent, 'activities') and hasattr(globals.config.agent, 'org'):
                _log.info('Running commands in offline mode')
                self.start()
                status = globals.APIStatus.SUCCESS
            
        return status       
       
class Controller(ExceptionThread):
    __metaclass__ = SingletonType
    
    def __init__(self):
        ExceptionThread.__init__(self)
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
            _log.info('Uninstalling agent')
            subprocess.Popen([self.globals.exe_path + 'uninstall.sh'])
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
            if self.handle_response(Connection().connect()) == False:
                break
                
            if self.globals.is_update_only_mode == False:            
                if self.globals.store.start() == False:
                    break

                if len(self.globals.config.agent.activities) == 0:
                    self.globals.store.clear_offline_data()

                self.globals.manage_activities();
                self.globals.stop_event.wait()
                _log.debug('Controller received stop event')
            else:
                while 1:
                    if self.globals.api.post_event.is_set() == False:
                        _log.debug('Controller waiting for post event')
                        self.globals.api.post_event.wait()
                    
                    if self.globals.stop_event.is_set():
                        _log.debug('Controller received stop event')
                        break
                    
                    self.globals.api.get_config()
                    self.globals.stop_event.wait(5 * 60)
            
            self.stop_threads()
            
            if self.handle_response(self.globals.api.stop_status) == False:
                break

            if self.is_stop == True:
                break

            self.globals.reset_interfaces()
        
        _log.debug('Controller generating SIGALRM signal')
        signal.alarm(2)
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
        
        if controller.is_alive() == False:
            globals.api.logout()
            quit()

