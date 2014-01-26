import threading
import sqlite3 as sqlite
import time
from constructs import *

class OfflineStore(threading.Thread):    
    def __init__(self, path, api):
        threading.Thread.__init__(self)
        self.path = path
        self.conn = None
        self.conn_event = threading.Event()
        self.api = api
        self.task_queue = queue.Queue()
        self.sender = None
        
    def start(self):
        threading.Thread.start(self)
        return self.wait()
        
    def wait(self):
        self.conn_event.wait()            
        return True if self.conn else False
    
    def send(self):
        if self.sender == None or self.sender.is_alive() == False:
            self.sender = Sender(self)
            self.sender.start()          
        
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
        
        self.send()
        
        while 1:
            try:
                task = self.task_queue.get(True, 5)
                getattr(self, task['op'])(**task['kwargs'])
            except:
                pass
                
            if self.api.stop_event.is_set():
                while 1:
                    try:
                        task = self.task_queue.get(False)
                        getattr(self, task['op'])(**task['kwargs'])                        
                    except:
                        break
                
                self.conn.close()
                break
    
    def insert(self, activity, data):
        try:
            self.cursor.execute('INSERT INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
            self.conn.commit()
            self.send()
        except:        
            return False        
        
        return True
    
    def select(self, arr = [], read_event = None):
        rows = self.cursor.execute('SELECT ROWID, * FROM data ORDER BY timestamp LIMIT 10')
        
        for row in rows:
            data = {
                'timestamp': row[2],
                'returnCode': row[3],
                'data': row[4]
            }
            
            arr.append({'row_id': row[0], 'activity': row[1], 'data': data})
         
        read_event and read_event.set()
        return arr
            
    def delete(self, row_ids):
        try:
            self.cursor.execute('DELETE FROM data WHERE ROWID IN (%s)' % ','.join('?' * len(row_ids)), row_ids)
            self.conn.commit()
        except:
            return False
        
        return True
    
    def truncate(self):
        try:
            self.cursor.execute('DELETE FROM data')
            self.conn.commit()
        except:
            return False
        
        return True
        
    def put(self, activity, data):
        print 'inserting'
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data}})
        
    def get(self):
        read_event = threading.Event()
        rows = []
        self.task_queue.put({'op': 'select', 'kwargs': {'read_event': read_event, 'arr': rows}})
        read_event.wait()
        return rows
        
    def rem(self, row_ids):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids}})
        
    def clr(self):
        self.task_queue.put({'op': 'truncate'})
    
class Sender(threading.Thread):    
    def __init__(self, off_store):
        threading.Thread.__init__(self)
        self.off_store = off_store
        
    def wait(self):
        self.off_store.api.post_event.wait()
        return False if self.off_store.api.stop_event.is_set() else True
        
    def run(self):
        while 1:
            rows = self.off_store.get()
            
            if len(rows) == 0 or self.wait() == False:
                break
                
            del_rows = []
            
            for i in range(0, len(rows)):
                if self.wait() == False:
                    return
                
                status = self.off_store.api.post_data(rows[i]['activity'], rows[i]['data'])
                
                if status == api.status.SUCCESS:
                    del_rows.append(rows[i]['row_id'])
                elif status == api.status.MISMATCH:
                    pass
                elif status == api.status.NOT_CONNECTED or status == api.status.NO_SERVICE:
                    break
            
            if len(del_rows):
                self.off_store.rem(del_rows)
