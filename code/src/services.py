import threading
from globals import Globals

class ActivityThread(threading.Thread):
    def __init__(self, activity):
        threading.Thread.__init__(self)
        ActivityThread.threadid = ActivityThread.threadid + 1
        self.threadid = ActivityThread.threadid
        self.activity = activity;

    def run(self):
        while 1:
            print 'Executing ' + self.activity['name']
            timestamp = int(round(time.time() * 1000))
            ret = ActivityThread.execute(self.activity['command'])
            print 'Sending ' + self.activity['name']
            data = {'returnCode': ret['returncode'], 'timestamp': timestamp, 'data': ret['output']}
            ActivityThread.session.post(get_complete_url('/1/data/activities/' + self.activity['_id']), data=data)
            time.sleep(self.activity['interval'])            

    @staticmethod
    def execute(command):
        ret = {};
        p = subprocess.Popen(['sh', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.communicate();
        ret['output'] = output[0] if output[0] else output[1]
        ret['returncode'] = p.returncode;
        return ret
    
class ConnectThread(threading.Thread):
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
    
def handle_conn_response(response):
    if response == False:
        print 'Failed to connect; exiting'
        exit()
    elif response and response != True:
        if response.status_code == 404:
            pass #uninstall agent

        print 'Failed to connect; exiting'
        exit()
    
def start():
    try:
        Globals()
    except RuntimeError, e:
        print e
        exit()
    
    response = ConnectThread().connect()
    handle_conn_response(response)
