import threading
import time
from globals import Globals

class Activity(threading.Thread):
    def __init__(self, activity, stop_event):
        threading.Thread.__init__(self)
        self.activity = activity;
        self.lock = threading.RLock()
        self.interval_event = threading.Event()
        self.stop_event = stop_event

    def run(self):
        while 1:
            if self.stop_event.is_set() or self.interval_event.is_set():
                break
                
            self.lock.acquire()
            print 'Executing ' + self.activity['name']
            timestamp = int(round(time.time() * 1000))
            ret = ActivityThread.execute(self.activity['command'])
            activity = self.activity['_id']
            self.lock.release()
            data = {'returnCode': ret['return_code'], 'timestamp': timestamp, 'data': ret['output']}
            t1 = int(time.time())
            Globals().api.post_data(activity, data = data)
            t2 = int(time.time())
            self.interval_event.wait(max(0, self.activity['interval'] - (t2 - t1)))

    @staticmethod
    def execute(command):
        ret = {};
        p = subprocess.Popen(['sh', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.communicate();
        ret['output'] = output[0] if output[0] else output[1]
        ret['return_code'] = p.returncode;
        return ret
    
    def set(self, activity):
        self.lock.acquire()
        self.activity = activity
        self.lock.release()
        
    def stop(self):
        self.interval_event.set()
    
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
        
        if res == None or res.status_code >= 500:
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
            globals.activities[activities[i]] = Activity(activities[i], globals.stop_event)
            globals.activities[activities[i]].start()

        globals.stop_event.wait()
        stop()        
        globals.reset()
    
