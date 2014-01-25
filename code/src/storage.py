import threading
import sqlite3 as sqlite
from constructs import *

class OfflineStore(threading.Thread):
    __metaclass__ = SingletonType
    
    def __init__(self, path = '', sync_event = None):
        threading.Thread.__init__(self)
        self.path = path
        self.conn = None
        self.conn_event = threading.Event()
        self.sync_event = sync_event or threading.Event
        self.task_queue = queue.Queue()
        self.read_queue = queue.Queue()
        
    def start(self):
        threading.Thread.start(self)
        return self.wait()
        
    def stop(self):
        self.conn and self.conn.close()
        
    def wait(self):
        if threading.current_thread().ident != self.ident:
            self.conn_event.wait()
            
        return True if self.conn else False
        
    def run(self):
        try:
            self.conn = sqlite.connect(self.path)
        except:
            return
        finally:
            self.conn_event.set()
            
        self.cursor = self.conn.cursor()
        
        try:
            self.cursor.execute('CREATE TABLE data(' + 
                'activity VARCHAR(50) NOT NULL, ' + 
                'timestamp INT NOT NULL, ' + 
                'return_code INT NOT NULL, ' + 
                'output BLOB NOT NULL, ' + 
                'PRIMARY KEY(activity, timestamp))')
        except:
            pass
        
        while 1:
            try:
                task = self.task_queue.get(True, 5)
                getattr(self, task['op'])(**task['kwargs'])
            except:
                pass
                
            if self.sync_event.is_set():
                self.close()
                break
    
    def insert(self, activity, data):
        try:
            self.cursor.execute('INSERT INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
            self.conn.commit()
        except:        
            return False        
        
        return True
    
    def select(self):
        items = self.cursor.execute('SELECT * FROM data ORDER BY timestamp LIMIT 10')
        
        for item in items:
            data = {
                'timestamp': item[1],
                'returnCode': item[2],
                'data': item[3]
            }
            
            self.read_queue.put({'activity': item[0], 'data': data})
            
        return True
            
    def delete(self, activity, timestamp):
        try:
            self.cursor.execute('DELETE FROM data WHERE activity = ? AND timestamp = ?', (activity, timestamp))
            self.conn.commit()
        except:
            return False
        
        return True
    
    def put(self, activity, data):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data}})
        
    def get(self):
        self.task_queue.put({'op': 'select'})
        
    def rem(self, activity, timestamp):
        self.task_queue.put({'op': 'delete', 'kwargs': {'activity': activity, 'timestamp': timestamp}})
    
    