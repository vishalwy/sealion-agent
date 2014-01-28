import pdb
import logging
import threading
import time
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
        self.task_queue.put({'op': 'close', 'kwargs': {}})
        
    def put(self, activity, data):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data}})
        
    def get(self, sender):
        self.task_queue.put({'op': 'select', 'kwargs': {'sender': sender}})
        
    def rem(self, row_ids, activities):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids, 'activities': activities}})
        
    def clr(self):
        self.task_queue.put({'op': 'truncate', 'kwargs': {}})
        
    def run(self):
        _log.debug('Starting up offline store')
        
        try:
            self.conn = sqlite.connect(self.path)
        except:
            _log.error('Failed to create offline storage at ' + self.path)
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
            
            if getattr(self, task['op'])(**task['kwargs']) == False:
                break
                
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
                
        return True
            
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
        _log.debug('Offline store received stop event')
        _log.debug('Offline store cleaning up queue')
        
        while 1:
            try:
                task = self.task_queue.get(False)
                getattr(self, task['op'])(**task['kwargs'])                        
            except:
                break

        _log.debug('Closing offline storage file')
        self.conn.close()
        return False
    
class Sender(threading.Thread):    
    def __init__(self, api, off_store):
        threading.Thread.__init__(self)
        self.api = api
        self.off_store = off_store
        self.queue = queue.Queue(maxsize = 100)
        
    def push(self, item):
        if self.api.post_event.is_set() == False:
            return False
        
        try:
            self.queue.put(item, False)
        except:
            return False
        
        return True
        
    def wait(self):
        _log.debug('Sender waiting for post event')
        self.api.post_event.wait()
        _log.debug('Sender received post event')
        
        if self.api.stop_event.is_set():
            _log.debug('Sender received stop event')
            return False
        
        return True
    
    def update_store(self, del_rows, del_activities):
        if len(del_rows) or len(del_activities):
            self.off_store.rem(del_rows, del_activities)
        
    def run(self):
        _log.debug('Starting up sender')
        api_status = self.api.status
        self.off_store.get(self)
        del_rows, del_activities = [], []
        
        while 1:
            if self.wait() == False:
                break
                
            try:
                item = self.queue.get(True, 5)
            except:
                if self.queue.full() == False:
                    self.update_store(del_rows, del_activities)
                    del_rows, del_activities = [], []
                    self.off_store.get(self)
                continue
                
            row_id = item.get('row_id')
            status = self.api.post_data(item['activity'], item['data'])
                
            if (status == api_status.SUCCESS or status == api_status.DATA_CONFLICT) and row_id:
                del_rows.append(row_id)
            elif status == api_status.MISMATCH:
                del_activities.append(item['activity'])
            elif (status == api_status.NOT_CONNECTED or status == api_status.NO_SERVICE) and row_id == None:
                self.off_store.put(item['activity'], item['data'])
                continue
                
        self.update_store(del_rows, del_activities)
        _log.debug('Sender cleaning up queue')
            
        while 1:
            try:
                item = self.queue.get(False)
                
                if item.get('row_id') == None:
                    self.off_store.put(item['activity'], item['data'])
            except:
                break
                
        self.off_store.stop()
        _log.debug('Shutting down sender')

class Interface:
    def __init__(self, path, api):
        self.off_store = OfflineStore(path)
        self.api = api
        self.sender = Sender(api, self.off_store)
        self.last_ping_time = int(time.time())
        
    def start(self):
        if self.off_store.start() == False:
            return False
        
        self.sender.start()
        return True
    
    def push(self, activity, data):
        if self.sender.push({'activity': activity, 'data': data}) == False:
            self.off_store.put(activity, data)
            
        t = int(time.time())
        
        if self.last_ping_time - t > 20:
            self.last_ping_time = t
            self.api.ping()
        
    def clear_offline_data(self):
        self.off_store.clr()