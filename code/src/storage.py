import threading
import sqlite3 as sqlite
from constructs import *

class OfflineStore(threading.Thread):    
    def __init__(self, path = '', stop_event = None):
        threading.Thread.__init__(self)
        self.path = path
        self.conn = None
        self.conn_event = threading.Event()
        self.stop_event = stop_event or threading.Event
        self.task_queue = queue.Queue()
        self.read_queue = queue.Queue()
        
    def start(self):
        threading.Thread.start(self)
        return self.wait()
        
    def stop(self):
        self.conn and self.conn.close()
        
    def wait(self):
        self.conn_event.wait()            
        return True if self.conn else False
        
    def run(self):
        try:
            self.conn = sqlite.connect(self.path)
        except:
            print 'Failed to create offline storage at ' + self.path
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
                
            if self.stop_event.is_set():
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
        rows = self.cursor.execute('SELECT ROWID, * FROM data ORDER BY timestamp LIMIT 10')
        
        for row in rows:
            data = {
                'timestamp': row[2],
                'returnCode': row[3],
                'data': row[4]
            }
            
            self.read_queue.put({'row_id': row[0], 'activity': row[1], 'data': data})
            
        return True
            
    def delete(self, row_ids):
        try:
            self.cursor.execute('DELETE FROM data WHERE ROWID IN (%s)' % ','.join('?' * len(row_ids)), row_ids)
            self.conn.commit()
        except:
            return False
        
        return True
    
    def put(self, activity, data):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data}})
        
    def get(self):
        self.task_queue.put({'op': 'select'})
        
    def rem(self, row_ids):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids}})
    
    
class Sender(threading.Thread):    
    def __init__(self, api = None, stop_event = None):
        threading.Thread.__init__(self)
        self.api = api
        self.stop_event = stop_event
        
    def run(self):
        self.api.post_event.wait()
        
        if self.stop_event.is_set():
            break
