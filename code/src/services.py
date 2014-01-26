import threading
import time
import subprocess
from globals import Globals

class Activity(threading.Thread):
    def __init__(self, activity, stop_event):
        threading.Thread.__init__(self)
        self.activity = activity;
        self.lock = threading.RLock()
        self.stop_event = stop_event
        self.is_stop = False

    def run(self):        
        while 1:           
            if self.stop_event.is_set() or self.stop(True) == True:
                break
                
            timestamp = int(round(time.time() * 1000))
            activity = self.activity['_id']
            command = self.activity['command']
            ret = Activity.execute(command)
            data = {'returnCode': ret['return_code'], 'timestamp': timestamp, 'data': ret['output']}
            t1 = int(time.time())
            Activity.send(activity, data)
            t2 = int(time.time())
            timeout = max(1, self.activity['interval'] - (t2 - t1))
            
            while timeout > 0:
                time.sleep(min(5, timeout))
                timeout -= 5
          
    @staticmethod
    def send(activity, data):
        globals = Globals()
                
        if globals.api.is_not_connected(globals.api.post_data(activity, data)):
            globals.off_store.put(activity, data)

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
        self.attempt()
    
    def attempt(self, max_try = -1):
        globals = Globals()
        status = globals.api.authenticate(max_try)
        status == globals.api.status.SUCCESS and globals.rtc.connect().start()
        return status            
        
    def connect(self):
        globals = Globals()
        
        if hasattr(globals.config.agent, '_id') == False and globals.api.register() != True:
            return False
        
        status = self.attempt(5)
        
        if globals.api.is_not_connected(status):
            if hasattr(globals.config.agent, 'activities'):
                self.start()
                status == globals.api.status.SUCCESS
            
        return status
    
def handle_conn_response(status):
    globals = Globals()
    
    if status == globals.api.status.SUCCESS:
        return
    
    stop()
    
    if globals.api.is_not_connected(status):
        print 'Failed to connect; exiting'
    elif status == globals.api.status.NOT_FOUND:
        print 'Uninstalling...'
    elif status == globals.api.status.UNAUTHERIZED or status == globals.api.status.BAD_REQUEST:
        print 'Unautherized or bad request; exiting'
        
    exit()
        
def stop():
    Globals().stop_event.set()
    threads = threading.enumerate()
    
    for thread in threads:
        thread.join()
    
def start():
    try:
        globals = Globals()
    except RuntimeError, e:
        print e
        exit()
        
    while 1:
        if globals.off_store.start() == False:
            exit()

        handle_conn_response(Connection().connect())
        activities = globals.config.agent.activities
        length = len(activities)
        
        if length == 0:
            globals.off_store.clr()

        for i in range(0, length):
            globals.activities[activities[i]['_id']] = Activity(activities[i], globals.stop_event)
            globals.activities[activities[i]['_id']].start()

        globals.stop_event.wait()
        stop()        
        globals.reset()
    
