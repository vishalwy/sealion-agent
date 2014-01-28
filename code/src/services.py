import logging
import threading
import time
import subprocess
import re
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
        _log.debug('Starting up activity')
        globals = Globals()
        
        while 1:                
            timestamp = int(round(time.time() * 1000))
            
            if self.is_whitelisted == True:
                ret = Activity.execute(self.activity['command'])
            else:
                ret = {'return_code': 0, 'output': 'Command blocked by whitelist.'}
                _log.info('Command ' + self.activity['_id'] + ' is blocked by whitelist')
                
            data = {'returnCode': ret['return_code'], 'timestamp': timestamp, 'data': ret['output']}
            _log.debug('Pushing ' + self.activity['_id'] + ' @ ' + str(timestamp) + ' to store')
            globals.store.push(self.activity['_id'], data)
            timeout = self.activity['interval']
            
            while timeout > 0:
                if self.stop_event.is_set() or self.stop(True) == True:
                    _log.debug('Shutting down activity')
                    return
                
                time.sleep(min(5, timeout))
                timeout -= 5

        _log.debug('Shutting down activity')

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
        self.attempt()
        _log.debug('Shutting down connection')
    
    def attempt(self, max_try = -1):
        globals = Globals()
        status = globals.api.authenticate(max_try)
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
    
def handle_conn_response(status):
    globals = Globals()

    if status == globals.APIStatus.SUCCESS:
        return
    
    stop()
    
    if globals.api.is_not_connected(status):
        _log.info('Failed to connect')
    elif status == globals.APIStatus.NOT_FOUND:
        _log.info('Uninstalling agent')
    elif status == globals.APIStatus.UNAUTHERIZED:
        _log.error('Agent unautherized to connect')
    elif status == globals.APIStatus.BAD_REQUEST:
        _log.error('Server marked the request as bad')
        
    quit()
        
def stop():
    _log.debug('Stopping all threads')
    Globals().api.stop()
    threads = threading.enumerate()
    curr_thread = threading.current_thread()
    
    for thread in threads:
        if thread.ident != curr_thread.ident:
            _log.debug('Waiting for ' + str(thread))
            thread.join()
            
def quit(status = 0):
    _log.info('Shutting down with status code ' + str(status))
    exit()
    
def start():
    globals = Globals()
    globals.activity_type = Activity
        
    while 1:
        if globals.store.start() == False:
            quit()

        handle_conn_response(Connection().connect())
        activities = globals.config.agent.activities
        length = len(activities)
        
        if length == 0:
            globals.store.clear_offline_data()
            
        globals.activities = {}

        for i in range(0, length):
            globals.activities[activities[i]['_id']] = Activity(activities[i], globals.stop_event)
            globals.activities[activities[i]['_id']].start()

        _log.debug('Waiting for stop event')
        globals.stop_event.wait()
        _log.debug('Received stop event')
        stop()        
        globals.reset()
    
