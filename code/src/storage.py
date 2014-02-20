import logging
import threading
import time
import gc
import sqlite3 as sqlite
from constructs import *
from helper import Utils

_log = logging.getLogger(__name__)

class OfflineStore(ThreadEx):    
    def __init__(self, db_path, config):
        ThreadEx.__init__(self)
        self.db_file = db_path
        self.config = config
        self.conn = None
        self.conn_event = threading.Event()
        self.task_queue = queue.Queue()
        
    def start(self):
        self.db_file = Utils.get_safe_path(self.db_file + ('%s.db' % self.config.agent.org))
        ThreadEx.start(self)
        self.conn_event.wait()            
        return True if self.conn else False
    
    def stop(self):
        self.task_queue.put({'op': 'close', 'kwargs': {}})
        
    def put(self, activity, data, callback = None):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data, 'callback': callback}})
        
    def get(self, limit, callback):
        self.task_queue.put({'op': 'select', 'kwargs': {'limit': limit, 'callback': callback}})
        
    def rem(self, row_ids, activities):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids, 'activities': activities}})
        
    def clr(self):
        self.task_queue.put({'op': 'truncate', 'kwargs': {}})
        
    def exe(self):
        _log.debug('Starting up offline store')
        
        try:
            self.conn = sqlite.connect(self.db_file)
            _log.debug('Created offline storage at ' + self.db_file)
        except Exception as e:
            _log.error('Failed to create offline storage at ' + self.db_file + '; ' + str(e))
            _log.debug('Shutting down offline store')
            self.conn_event.set()
            return
            
        self.cursor = self.conn.cursor()
        
        if self.setup_schema() == False:
            _log.error('Schema mismatch in offline storage at ' + self.db_file)
            self.close_db()
            _log.debug('Shutting down offline store')
            self.conn_event.set()
            return
        
        self.conn_event.set()
        
        while 1:
            task = self.task_queue.get()
            
            if getattr(self, task['op'])(**task['kwargs']) == False:
                break
                
        _log.debug('Shutting down offline store')
        
    def setup_schema(self):
        is_existing_table = True
        
        #(index, col_name, col_type, not_null, default, pk)
        schema = [
            (0, 'activity', 'VARCHAR(50)', 1, None, 1),
            (1, 'timestamp', 'INT', 1, None, 1), 
            (2, 'return_code', 'INT', 1, None, 0), 
            (3, 'output', 'BLOB', 1, None, 0)
        ]
                
        try:
            columns, pk = '', ''
            
            for col in schema:
                not_null = 'NOT NULL' if col[3] == 1 else 'NULL'
                default = '' if col[4] == None else col[4]
                columns += '%s%s %s %s %s' % (', ' if len(columns) else '', col[1], col[2], not_null, default)
                pk += (', ' if len(pk) else '') + col[1] if col[5] == 1 else ''
            
            pk = (', PRIMARY KEY(%s)' % pk) if len(pk) else ''
            query = 'CREATE TABLE data(%s%s)' % (columns, pk)
            self.cursor.execute(query)
            is_existing_table = False
        except:
            pass
        
        if is_existing_table == True:
            try:
                self.cursor.execute('PRAGMA TABLE_INFO(data)')
                schema = set(schema)
                cur_schema = set(self.cursor.fetchall())

                if len(schema - cur_schema) > 0 or len(cur_schema - schema) > 0:
                    return False
            except:
                return False
            
        return True
    
    def insert(self, activity, data, callback = None):
        try:
            self.cursor.execute('INSERT INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
            self.conn.commit()
            _log.debug('Inserted activity(%s @ %d) to offline storage' % (activity, data['timestamp']))
            callback and callback()
        except Exception as e:
            _log.error('Failed to insert rows to offline storage; ' + str(e))
        
        return True
    
    def select(self, limit, callback):        
        try:
            rows = self.cursor.execute('SELECT ROWID, * FROM data ORDER BY timestamp LIMIT %d' % limit)
        except Exception as e:
            _log.error('Failed to retreive rows from offline storage; ' + str(e))
            return True
        
        rows = self.cursor.fetchall()
        _log.debug('Retreived %d rows from offline storage' % len(rows))
        callback(rows)
        return True
            
    def delete(self, row_ids = [], activities = []):
        try:
            format = (','.join('?' * len(row_ids)), ','.join('?' * len(activities)))
            self.cursor.execute('DELETE FROM data WHERE ROWID IN (%s) OR activity IN (%s)' % format, row_ids + activities)
            self.conn.commit()
            _log.debug('Deleted ' + str(self.cursor.rowcount) + ' records from offline storage')
        except Exception as e:
            _log.error('Failed to delete rows from offline storage; ' + str(e))
        
        return True
    
    def truncate(self):
        try:
            self.cursor.execute('DELETE FROM data')
            self.conn.commit()
            _log.debug('Deleting all records from offline storage')
        except Exception as e:
            _log.error('Failed to truncate offline storage; ' + str(e))
        
        return True
    
    def close_db(self):
        _log.debug('Closing offline storage at ' + self.db_file)
        self.conn.close()
        self.conn = None
    
    def close(self):
        _log.debug('Offline store received stop event')
        _log.debug('Offline store cleaning up queue')
        
        while 1:
            try:
                task = self.task_queue.get(False)
                
                if task['op'] != 'select' and task['op'] != 'close':
                    getattr(self, task['op'])(**task['kwargs'])                        
            except:
                break

        self.close_db()
        return False
    
class Sender(ThreadEx):   
    queue_max_size = 100
    ping_interval = 10
    
    def __init__(self, api, off_store):
        ThreadEx.__init__(self)
        self.api = api
        self.off_store = off_store
        self.queue = queue.Queue(self.queue_max_size)
        self.lock = threading.RLock()
        self.store_data_available = True
        self.last_ping_time = int(time.time())
        
    def push(self, item):
        try:
            self.queue.put(item, False)
        except:
            return False
        finally:
            t = int(time.time())
        
            if self.last_ping_time - t > self.ping_interval:
                self.last_ping_time = t
                self.api.ping()
        
        return True
        
    def wait(self):
        if self.api.post_event.is_set() == False:
            _log.debug('GC collected %d unreachables' % gc.collect())
            timeout = self.ping_interval if self.api.is_authenticated else None
            _log.debug('Sender waiting for post event' + (' for %d seconds' % timeout if timeout else ''))
            self.api.post_event.wait(timeout)
        
        if self.api.stop_event.is_set():
            _log.debug('Sender received stop event')
            return False
        
        return True
    
    def update_store(self, del_rows, del_activities):
        if len(del_rows) or len(del_activities):
            self.off_store.rem(del_rows, del_activities)
            
    def store_available(self, is_available = None):
        self.lock.acquire()
        
        if is_available == None:
            is_available = self.store_data_available
        else:
            if is_available == True and self.store_data_available == False:
                _log.debug('Marking offline store available')
                self.store_data_available = True
            elif is_available == False and self.store_data_available == True:
                _log.debug('Marking offline store not available')
                self.store_data_available = False
            
        self.lock.release()
        return is_available
    
    def store_get_callback(self, rows):
        row_count, i = len(rows), 0
        
        while i < row_count:            
            data = {
                'timestamp': rows[i][2],
                'returnCode': rows[i][3],
                'data': rows[i][4]
            }
            
            if self.push({'row_id': rows[i][0], 'activity': rows[i][1], 'data': data}) == False:
                break
                
            i += 1
        
        _log.debug('Pushed %d rows to sender from offline storage' % i)
        self.store_available(i != row_count or self.queue_max_size == row_count)
        
    def store_put_callback(self):
        self.store_available(True)
        
    def exe(self):
        _log.debug('Starting up sender')
        api_status = self.api.status
        del_rows, del_activities, gc_counter, gc_threshold = [], [], 0, 2
        
        while 1:
            if self.wait() == False:
                break
                
            try:
                item = self.queue.get(True, 5)
                gc_counter = 1
                
                if any(a for a in del_activities if a == item['activity']):
                    _log.debug('Discarding activity %s' % item['activity'])
                    continue
            except:
                self.update_store(del_rows, del_activities)
                del_rows, del_activities = [], []
                gc_counter = gc_counter + 1 if gc_counter else 0
                    
                if gc_counter == gc_threshold:
                    _log.debug('GC collected %d unreachables' % gc.collect())
                    gc_counter = 0
                
                if self.store_available():
                    self.off_store.get(self.queue_max_size, self.store_get_callback)
                
                continue
                
            row_id = item.get('row_id')
            status = self.api.post_data(item['activity'], item['data'])
                
            if (status == api_status.SUCCESS or status == api_status.DATA_CONFLICT) and row_id:
                del_rows.append(row_id)
            elif status == api_status.MISMATCH:
                any(a for a in del_activities if a == item['activity']) == False and del_activities.append(item['activity'])
            elif (status == api_status.NOT_CONNECTED or status == api_status.NO_SERVICE):
                row_id == None and self.off_store.put(item['activity'], item['data'], self.store_put_callback)
                
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
    def __init__(self, api, db_path):
        self.api = api
        self.off_store = OfflineStore(db_path, api.config)
        self.sender = Sender(api, self.off_store)
        
    def start(self):        
        if self.off_store.start() == False:
            return False
        
        self.sender.start()
        return True
    
    def push(self, activity, data):
        if self.sender.push({'activity': activity, 'data': data}) == False:
            self.off_store.put(activity, data, self.sender.store_put_callback)
        
    def clear_offline_data(self):
        self.off_store.clr()
