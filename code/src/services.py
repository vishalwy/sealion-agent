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
        globals = Globals()
        
        while 1:           
            if self.stop_event.is_set() or self.stop() == True:
                break
                
            timestamp = int(round(time.time() * 1000))
            activity = self.activity['_id']
            command = self.activity['command']
            ret = Activity.execute(command)
            data = {'returnCode': ret['return_code'], 'timestamp': timestamp, 'data': ret['output']}
            t1 = int(time.time())
            globals.api.post_data(activity, data)
            t2 = int(time.time())
            timeout = max(1, self.activity['interval'] - (t2 - t1))
            
            while timeout > 0:
                time.sleep(min(5, timeout))
                timeout -= 5

    @staticmethod
    def execute(command):
        ret = {};
        p = subprocess.Popen(['sh', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.communicate();
        ret['output'] = output[0] if output[0] else output[1]
        ret['return_code'] = p.returncode;
        return ret
        
    def stop(self, is_stop = None):
        self.lock.acquire()
        
        if is_stop != None:
           self.is_stop = is_stop
        else:
            is_stop = self.is_stop
        
        self.lock.release()
        return is_stop
    
class Connection(threading.Thread):
    def run(self):
        self.attempt()
    
    def attempt(self, max_try = -1):
        globals = Globals()
        res = globals.api.authenticate(max_try)
        res == True and globals.rtc.connect().start()
        return res            
        
    def connect(self):
        globals = Globals()
        
        if hasattr(globals.config.agent, '_id') == False and globals.api.register() != True:
            return False
        
        res = self.attempt(5)
        
        if res == None or (type(res) is not bool and res.status_code >= 500):
            res = hasattr(globals.config.agent, 'activities')
            res and self.start()            
            
        return res  
    
def handle_conn_response(response):
    if response == False:
        print 'Failed to connect; exiting'
        stop()
        exit()
    elif response and response != True:
        if response.status_code == 404:
            print 'Uninstalling...'
        else:
            print 'Failed to connect; exiting'
        
        stop()
        exit()
        
def stop():
    globals.stop_event.set()
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

        for i in range(0, len(activities)):
            globals.activities[activities[i]['_id']] = Activity(activities[i], globals.stop_event)
            globals.activities[activities[i]['_id']].start()

        globals.stop_event.wait()
        stop()        
        globals.reset()
    
