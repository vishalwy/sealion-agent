import threading
import sqlite3 as sqlite
from constructs import *

class OfflineStore(threading.Thread):    
    def __init__(self, path = '', sync_event = None):
        threading.Thread.__init__(self)
        self.path = path
        self.conn = None
        self.conn_event = threading.Event()
        self.sync_event = sync_event or threading.Event
        
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
            if self.sync_event.is_set():
                self.close()
                break
    
    def put(self, activity, data):
        try:
            self.cursor.execute('INSERT INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
            self.conn.commit()
        except:        
            return False        
        
        return True
    
    def get(self):
        return None
    
    