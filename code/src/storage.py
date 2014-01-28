import logging
import threading
import sqlite3 as sqlite
from constructs import *

_log = logging.getLogger(__name__)

class OfflineStore(threading.Thread):    
    def __init__(self, path):
        threading.Thread.__init__(self)
        self.path = path
        self.conn = None
        self.conn_event = threading.Event()
        self.task_queue = queue.Queue()
        
    def start(self):
        threading.Thread.start(self)
        self.conn_event.wait()            
        return True if self.conn else False
    
    def stop(self):
        self.task_queue.put({'op': 'stop'})
        
    def put(self, activity, data):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data}})
        
    def get(self, sender):
        self.task_queue.put({'op': 'select', 'kwargs': {'sender': sender}})
        
    def rem(self, row_ids, activities):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids, 'activities': activities}})
        
    def clr(self):
        self.task_queue.put({'op': 'truncate'})
        
    def run(self):
        _log.debug('Starting up offline store')
        
        try:
            self.conn = sqlite.connect(self.path)
        except:
            _log.error('Failed to create offline store at ' + self.path)
            _log.debug('Shutting down offline store')
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
            task = self.task_queue.get()
            getattr(self, task['op'])(**task['kwargs'])
                
        _log.debug('Shutting down offline store')
    
    def insert(self, activity, data):
        try:
            self.cursor.execute('INSERT INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
            self.conn.commit()
            _log.debug('Inserted ' + activity + ' @ ' + str(data['timestamp']) + ' to offline store')
        except:        
            return False        
        
        return True
    
    def select(self, sender):
        rows = self.cursor.execute('SELECT ROWID, * FROM data ORDER BY timestamp LIMIT 10')
        
        for row in rows:
            data = {
                'timestamp': row[2],
                'returnCode': row[3],
                'data': row[4]
            }
            
            if sender.push({'row_id': row[0], 'activity': row[1], 'data': data}) == False:
                break
            
    def delete(self, row_ids = [], activities = []):
        try:
            format = (','.join('?' * len(row_ids)), ','.join('?' * len(activities)))
            self.cursor.execute('DELETE FROM data WHERE ROWID IN (%s) OR activity IN (%s)' % format, row_ids + activities)
            self.conn.commit()
            _log.debug('Deleted ' + str(self.cursor.rowcount) + ' records from offline store')
        except:
            return False
        
        return True
    
    def truncate(self):
        try:
            self.cursor.execute('DELETE FROM data')
            self.conn.commit()
            _log.debug('Deleting all records from offline store')
        except:
            return False
        
        return True
    
    def close(self):
        _log.debug('Offline store received stop event; cleaning up queue')
        
        while 1:
            try:
                task = self.task_queue.get(False)
                getattr(self, task['op'])(**task['kwargs'])                        
            except:
                break

        _log.debug('Closing offline store file')
        self.conn.close()
    
class Sender(threading.Thread):    
    def __init__(self, off_store):
        threading.Thread.__init__(self)
        self.off_store = off_store
        self.queue = queue.Queue(maxsize = 100)
        
    def push(self, item):
        try:
            self.queue.put(item, False)
        except:
            return False
        
        return True
        
    def wait(self):
        _log.debug('Sender waiting for post event')
        self.off_store.api.post_event.wait()
        _log.debug('Sender received post event')
        
        if self.off_store.api.stop_event.is_set():
            _log.debug('Sender received stop event')
            return False
        
        return True
        
    def run(self):
        _log.debug('Starting up Sender')
        api_status = self.off_store.api.status
        
        while 1:
            self.off_store.get(self)
            
            if self.wait() == False:
                break
                
            try:
                item = self.queue.get(True, 5)
            except:
                continue
                
            del_activities = []
            del_rows = [item['row_id']] if item.has_key('row_id') else []

            if self.off_store.api.post_data(item['activity'], item['data']) == api_status.MISMATCH:
                del_activities.append(item['activity'])
                
            if len(del_rows) or len(del_activities):
                self.off_store.rem(del_rows, del_activities)
            
        _log.debug('Shutting down offline store sender')

class Interface:
    def __init__(self, path, api):
        self.api = api
        self.off_store = OfflineStore(path)
        self.sender = Sender(self.off_store)
        
    def start(self):
        if self.off_store.start() == False:
            return False
        
        self.sender.start()
        return True
    
    def push(self, activity, data):
        if sender.push({'activity': activity, 'data': data}) == False:
            self.off_store.put(activity, data)
        