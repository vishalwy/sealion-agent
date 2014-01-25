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
            if self.stop_event.is_set():
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
            self.interval_event.clear()

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
    
class Connection(threading.Thread):
    def run(self):
        self.attempt(-1)
    
    def attempt(self, max_try = 5):
        globals = Globals()
        res = globals.api.authenticate(max_try)
        res == True and globals.rtc.connect().start()
        return res            
        
    def connect(self):
        globals = Globals()
        
        if hasattr(globals.config.agent, '_id') == False and globals.api.register() != True:
            return False
        
        res = self.attempt()
        
        if res == None:
            res = hasattr(globals.config.agent, 'activities')
            res and self.start()            
            
        return res  
    
    def join(self):
        globals = Globals()
        self.is_alive() and threading.Thread.join(self)
        globals.rtc.is_alive() and globals.rtc.join()
    
def handle_conn_response(response):
    if response == False:
        print 'Failed to connect; exiting'
        exit()
    elif response and response != True:
        if response.status_code == 404:
            print 'Uninstalling...'
        else:
            print 'Failed to connect; exiting'
            
        exit()
    
def start():
    try:
        globals = Globals()
    except RuntimeError, e:
        print e
        exit()
        
    if globals.off_store.start() == False:
        exit()
        
    conn = Connection()
    handle_conn_response(conn.connect())
    activities = globals.config.agent.activities
    
    for i in range(0, len(activities)):
        globals.activities[activities[i]] = Activity(activities[i], globals.stop_event).start()
        
    globals.stop_event.wait()
    
    for i in range(0, len(activities)):
        globals.activities[activities[i]].join()
        
    conn.join()
    globals.off_store.join()
    
