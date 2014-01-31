import logging
import threading
import time
import subprocess
import re
import signal
from constructs import *
from globals import Globals

_log = logging.getLogger(__name__)

class Activity(threading.Thread):
    def __init__(self, activity, stop_event):
        threading.Thread.__init__(self)
        self.activity = activity;
        self.lock = threading.RLock()
        self.stop_event = stop_event
        self.is_stop = False
        self.is_whitelisted = self.is_in_whitelist()
        
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

    def run(self):
        _log.debug('Starting up activity %s' % self.activity['_id'])
        globals = Globals()
        
        while 1:                
            timestamp = int(round(time.time() * 1000))
            
            if self.is_whitelisted == True:
                ret = Activity.execute(self.activity['command'])
            else:
                ret = {'return_code': 0, 'output': 'Command blocked by whitelist.'}
                _log.info('Command ' + self.activity['_id'] + ' is blocked by whitelist')
                
            data = {'returnCode': ret['return_code'], 'timestamp': timestamp, 'data': ret['output']}
            _log.debug('Pushing activity(%s @ %d) to store' % (self.activity['_id'], timestamp))
            globals.store.push(self.activity['_id'], data)
            timeout = self.activity['interval']
            break_flag = False
            
            while timeout > 0:
                if self.stop_event.is_set() or self.stop(True) == True:
                    _log.debug('Activity %s received stop event' % self.activity['_id'])
                    break_flag = True
                    break
                
                time.sleep(min(5, timeout))
                timeout -= 5
                
            if break_flag == True:
                break

        _log.debug('Shutting down activity %s' % self.activity['_id'])

    @staticmethod
    def execute(command):
        ret = {};
        p = subprocess.Popen(['sh', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.communicate();
        ret['output'] = output[0] if output[0] else output[1]
        ret['return_code'] = p.returncode;
        return ret
        
    def stop(self, is_query = None):
        is_stop = True
        self.lock.acquire()
        
        if is_query == True:
            is_stop = self.is_stop
        else:
            self.is_stop = is_stop
            
        self.lock.release()
        return is_stop
    
class Connection(threading.Thread):
    def run(self):
        _log.debug('Starting up connection')
        self.attempt(retry_interval = 20)
        _log.debug('Shutting down connection')
    
    def attempt(self, max_try = -1, retry_interval = 5):
        globals = Globals()
        status = globals.api.authenticate(max_try, retry_interval)
        status == globals.APIStatus.SUCCESS and globals.rtc.connect().start()
        return status            
        
    def connect(self):
        globals = Globals()
        status = globals.APIStatus.SUCCESS
        
        if hasattr(globals.config.agent, '_id') == False:
            status = globals.api.register()
            
        if status != globals.APIStatus.SUCCESS:
            return status
        
        status = self.attempt(2)
        
        if globals.api.is_not_connected(status):
            if hasattr(globals.config.agent, 'activities'):
                _log.info('Running commands in offline mode')
                self.start()
                status = globals.APIStatus.SUCCESS
            
        return status
       
class Controller(threading.Thread):
    __metaclass__ = SingletonType
    
    def __init__(self):
        threading.Thread.__init__(self)
        self.globals = Globals()
        self.lock = threading.RLock()
        self.is_stop = False
        self.main_thread = threading.current_thread()
    
    def handle_response(self, status):
        if status == self.globals.APIStatus.SUCCESS:
            return True
        elif status == self.globals.APIStatus.AGENT_UPDATE:
            _log.info('Stoping agent for update')
        elif self.globals.api.is_not_connected(status):
            _log.info('Failed to connect')
        elif status == self.globals.APIStatus.NOT_FOUND:
            _log.info('Uninstalling agent')
        elif status == self.globals.APIStatus.UNAUTHERIZED:
            _log.error('Agent unautherized to connect')
        elif status == self.globals.APIStatus.BAD_REQUEST:
            _log.error('Server marked the request as bad')
        elif status == self.globals.APIStatus.SESSION_CONFLICT:
            _log.error('Agent session conflict')

        return False
        
    def run(self):
        while 1:
            _log.debug('Controller starting up')
            
            if self.globals.store.start() == False:
                break

            if self.handle_response(Connection().connect()) == False:
                break

            if len(self.globals.config.agent.activities) == 0:
                self.globals.store.clear_offline_data()

            self.globals.manage_activities();
            _log.debug('Controller waiting for stop event')
            self.globals.stop_event.wait()
            _log.debug('Controller received stop event')
            self.stop_threads()
            
            if self.handle_response(self.globals.api.stop_status) == False:
                break

            if self.stop(True) == True:
                break

            self.globals.reset()
        
        _log.debug('Controller generating SIGALRM signal')
        signal.alarm(2)
        _log.debug('Controller shutting down')
            
    def stop(self, is_query = None):
        is_stop = True
        self.lock.acquire()
        
        if is_query == True:
            is_stop = self.is_stop
        else:
            self.is_stop = is_stop
            self.globals.api.stop()
            
        self.lock.release()
        return is_stop
        
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
    _log.info('Shutting down with status code %d' % status)
    exit(status)
    
def start():
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
            globals.stop_event.clear()
            globals.api.logout()
            quit()

