import logging
import threading
import sqlite3 as sqlite
from constructs import *

_log = logging.getLogger(__name__)

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
        _log.debug('Starting up offline store ' + str(self))
        
        try:
            self.conn = sqlite.connect(self.path)
        except:
            _log.error('Failed to create offline store at ' + self.path)
            _log.debug('Shutting down offline store ' + str(self))
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
                _log.debug('Offline store received stop event; cleaning up queue ' + str(self))
                
                while 1:
                    try:
                        task = self.task_queue.get(False)
                        getattr(self, task['op'])(**task['kwargs'])                        
                    except:
                        break
                
                self.conn.close()
                break
                
        _log.debug('Shutting down offline store ' + str(self))
    
    def insert(self, activity, data):
        try:
            self.cursor.execute('INSERT INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
            self.conn.commit()
            _log.debug('Inserted ' + activity + ' @ ' + str(data['timestamp']) + ' to offline store')
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
        
    def put(self, activity, data):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data}})
        
    def get(self):
        read_event = threading.Event()
        rows = []
        self.task_queue.put({'op': 'select', 'kwargs': {'read_event': read_event, 'arr': rows}})
        read_event.wait()
        return rows
        
    def rem(self, row_ids, activities):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids, 'activities': activities}})
        
    def clr(self):
        self.task_queue.put({'op': 'truncate'})
    
class Sender(threading.Thread):    
    def __init__(self, off_store):
        threading.Thread.__init__(self)
        self.off_store = off_store
        
    def wait(self):
        _log.debug('Offline store sender waiting for post event ' + str(self))
        self.off_store.api.post_event.wait()
        _log.debug('Offline store sender received post event ' + str(self))
        
        if self.off_store.api.stop_event.is_set():
            _log.debug('Offline store sender received stop event ' + str(self))
            return False
        
        return True
        
    def run(self):
        _log.debug('Starting up offline store sender ' + str(self))
        
        while 1:
            _log.debug('Offline store sender waiting for rows ' + str(self))
            rows = self.off_store.get()
            row_count, i = len(rows), 0
            _log.debug('Offline store sender got ' + str(row_count) + ' rows ' + str(self))
            
            if row_count == 0 or self.wait() == False:
                break
                
            del_rows = []
            del_activities = []
            
            while i < row_count:
                if self.wait() == False:
                    _log.debug('Shutting down offline store sender ' + str(self))
                    return
                
                status = self.off_store.api.post_data(rows[i]['activity'], rows[i]['data'])
                api_status = self.off_store.api.status
                
                if status == api_status.SUCCESS or status == api_status.DATA_CONFLICT:
                    del_rows.append(rows[i]['row_id'])
                elif status == api_status.MISMATCH:
                    del_activities.append(rows[i]['activity'])
                    j = i + 1
                    
                    while j < row_count:
                        if rows[i]['activity'] == rows[j]['activity']:
                            rows.pop(j)
                            row_count -= 1
                        else:
                            j += 1
                    
                elif status == api_status.NOT_CONNECTED or status == api_status.NO_SERVICE:
                    break
                    
                i += 1
            
            self.off_store.rem(del_rows, del_activities)
            
        _log.debug('Shutting down offline store sender ' + str(self))
