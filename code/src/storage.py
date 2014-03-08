import logging
import threading
import time
import gc
import sqlite3
import helper
import globals
import api
from constructs import *

_log = logging.getLogger(__name__)

class OfflineStore(ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = globals.Interface()
        self.db_file = self.globals.db_path
        self.conn = None
        self.conn_event = threading.Event()
        self.task_queue = queue.Queue()
        self.is_bulk_insert = False
        self.bulk_insert_rows = []
        
    def start(self):
        self.db_file = helper.Utils.get_safe_path(self.db_file + ('%s.db' % self.globals.config.agent.org))
        ThreadEx.start(self)
        self.conn_event.wait()            
        return True if self.conn else False
    
    def stop(self):
        self.task_queue.put({'op': 'close', 'kwargs': {}})
        
    def put(self, activity, data, callback = None):
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data, 'callback': callback}})
        
    def put_bulk(self, rows):
        self.task_queue.put({'op': 'insert_bulk', 'kwargs': {'rows': rows}})
        
    def get(self, limit, callback):
        self.task_queue.put({'op': 'select', 'kwargs': {'limit': limit, 'callback': callback}})
        
    def rem(self, row_ids, activities):
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids, 'activities': activities}})
        
    def clr(self):
        self.task_queue.put({'op': 'truncate', 'kwargs': {}})
        
    def set_bulk_insert(self, is_bulk_insert):
        self.is_bulk_insert = is_bulk_insert
        
    def exe(self):        
        try:
            self.conn = sqlite3.connect(self.db_file)
            _log.debug('Created %s at %s' % (self.name, self.db_file))
        except Exception as e:
            _log.error('Failed to create %s at %s; %s' % (self.name, self.db_file, str(e)))
            self.conn_event.set()
            return
            
        self.cursor = self.conn.cursor()
        
        if self.setup_schema() == False:
            _log.error('Schema mismatch in %s at %s' % (self.name, self.db_file))
            self.close_db()
            self.conn_event.set()
            return
        
        self.conn_event.set()
        
        while 1:
            task = self.task_queue.get()
            
            if self.perform_task(task) == False:
                break
        
    def perform_task(self, task):
        is_insert = False
            
        if self.is_bulk_insert == True:
            if task['op'] == 'insert':
                self.bulk_insert_rows.append({'activity': task['kwargs']['activity'], 'data': task['kwargs']['activity']})
                is_insert = True
            elif task['op'] == 'insert_bulk':
                self.bulk_insert_rows += task['kwargs']['rows']
                is_insert = True
                
        if is_insert == False:
            len(self.bulk_insert_rows) and getattr(self, 'insert_bulk')(**{'rows': self.bulk_insert_rows})
            self.bulk_insert_rows = []
        else:
            return True

        return getattr(self, task['op'])(**task['kwargs'])
        
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
            _log.debug('Inserted activity(%s @ %d) to %s' % (activity, data['timestamp'], self.name))
            callback and callback()
        except Exception as e:
            _log.error('Failed to insert row to %s; %s' % (self.name, str(e)))
        
        return True
    
    def insert_bulk(self, rows):        
        row_count = 0
        
        try:
            for row in rows:
                activity = row['activity']
                data = row['data']
                self.cursor.execute('INSERT OR IGNORE INTO data VALUES(?, ?, ?, ?)', (activity, data['timestamp'], data['returnCode'], data['data']))
                row_count += self.cursor.rowcount
        
            self.conn.commit()
            _log.debug('Inserted %d rows to %s' % (row_count, self.name))
        except Exception as e:
            _log.error('Failed to insert rows to %s; %s' % (self.name, str(e)))
        
        return True
    
    def select(self, limit, callback):        
        try:
            rows = self.cursor.execute('SELECT ROWID, * FROM data ORDER BY timestamp DESC LIMIT %d' % limit)
        except Exception as e:
            _log.error('Failed to retreive rows from %s; %s' % (self.name, str(e)))
            return True
        
        rows = self.cursor.fetchall()
        _log.debug('Retreived %d rows from %s' % (len(rows), self.name))
        callback(rows)
        return True
            
    def delete(self, row_ids = [], activities = []):
        try:
            format = (','.join('?' * len(row_ids)), ','.join('?' * len(activities)))
            self.cursor.execute('DELETE FROM data WHERE ROWID IN (%s) OR activity IN (%s)' % format, row_ids + activities)
            self.conn.commit()
            _log.debug('Deleted %d records from %s' % (self.cursor.rowcount, self.name))
        except Exception as e:
            _log.error('Failed to delete rows from %s; %s' % (self.name, str(e)))
        
        return True
    
    def truncate(self):
        try:
            self.cursor.execute('DELETE FROM data')
            self.conn.commit()
            _log.debug('Deleting all records from %s' % self.name)
        except Exception as e:
            _log.error('Failed to truncate %s; %s' % (self.name, str(e)))
        
        return True
    
    def close_db(self):
        _log.debug('Closing %s at %s' % (self.db_file, self.name))
        self.conn.close()
        self.conn = None
    
    def close(self):
        _log.debug('%s received stop event' % self.name)
        _log.debug('%s cleaning up queue' % self.name)
        
        while 1:
            try:
                task = self.task_queue.get(False)
                
                if task['op'] != 'select' and task['op'] != 'close':
                    self.perform_task(task)
            except:
                break

        self.close_db()
        return False
   
class Sender(ThreadEx):   
    queue_max_size = 100
    ping_interval = 10
    gc_counter = 0
    gc_threshold = 2
    off_store_lock = threading.RLock()
    store_data_available = True
    
    def __init__(self, off_store):
        ThreadEx.__init__(self)
        self.globals = globals.Interface()
        self.api = api.Interface()
        self.off_store = off_store
        self.queue = queue.Queue(self.queue_max_size)
        self.last_ping_time = int(time.time())
        self.valid_activities = None
        
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
        if self.globals.post_event.is_set() == False:
            Sender.gc_counter and _log.debug('GC collected %d unreachables' % gc.collect())
            Sender.gc_counter = 0
            timeout = self.ping_interval if self.api.is_authenticated else None
            _log.debug('%s waiting for post event %s' % (self.name, ' for %d seconds' % timeout if timeout else ''))
            self.globals.post_event.wait(timeout)
        
        if self.globals.stop_event.is_set() == True:
            _log.debug('%s received stop event' % self.name)
            return False
        
        return True
            
    @staticmethod
    def store_available(is_available = None):
        Sender.off_store_lock.acquire()
        
        if is_available == None:
            is_available = Sender.store_data_available
        else:
            if is_available == True and Sender.store_data_available == False:
                _log.debug('Marking %s available' % Sender.off_store.__class__.__name__)
                Sender.store_data_available = True
            elif is_available == False and Sender.store_data_available == True:
                _log.debug('Marking %s not available' % Sender.off_store.__class__.__name__)
                Sender.store_data_available = False
            
        Sender.off_store_lock.release()
        return is_available
        
    def exe(self):       
        while 1:
            if self.wait() == False:
                break
                
            try:
                item = self.queue.get(True, 5)
                Sender.gc_counter = 1 if Sender.gc_counter == 0 else Sender.gc_counter 
                self.validate_count = max(self.validate_count - 1, 0)
                
                if self.validate_count and self.is_valid_activity(item['activity']) == False:
                    _log.debug('Discarding activity %s' % item['activity'])                    
                    continue
            except:
                Sender.gc_counter = Sender.gc_counter + 1 if Sender.gc_counter else 0
                    
                if Sender.gc_counter >= Sender.gc_threshold:
                    _log.debug('GC collected %d unreachables' % gc.collect())
                    Sender.gc_counter = 0
                    
                self.queue_empty()
                continue
                
            self.post_data(item)
                
        self.cleanup()
        
    def is_valid_activity(self, activity_id):
        ret = EmptyClass()
        self.globals.event_dispatcher.trigger('get_activity', activity_id, lambda x: [True, setattr(ret, 'value', x)][0])
        return ret.value != None
    
    def queue_empty(self):
        pass
    
    def cleanup(self):
        pass
    
    def post_data(self, item):
        pass
            
class RealtimeSender(Sender):        
    def post_data(self, item):
        api_status = self.api.status
        status = self.api.post_data(item['activity'], item['data'])

        if status == api_status.MISMATCH:
            self.api.get_config()
        elif (status == api_status.NOT_CONNECTED or status == api_status.NO_SERVICE):
            self.off_store.put(item['activity'], item['data'], self.store_put_callback)
            
    def cleanup(self):
        self.off_store.set_bulk_insert(True)
        rows = []
            
        while 1:
            try:
                rows.append(self.queue.get(False))
            except:
                break
                
        len(rows) and self.off_store.put_bulk(rows)
        self.off_store.stop()
        
    def store_put_callback(self):
        Sender.store_available(True)
    
class HistoricSender(Sender):
    def __init__(self, off_store):
        Sender.__init__(self, off_store)
        self.del_rows = []
        self.queue_max_size = 50
        
    def queue_empty(self):
        if len(self.del_rows):
            self.off_store.rem(self.del_rows, [])
            self.del_rows = []
        
        if Sender.store_available():
            self.off_store.get(self.queue_max_size, self.store_get_callback)
        
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
        
        _log.debug('Pushed %d rows to %s from %s' % (i, self.name, self.off_store.__class__.__name__))
        Sender.store_available(i != row_count or self.queue_max_size == row_count)
        
    def post_data(self, item):
        row_id, api_status = item.get('row_id'), self.api.status
        status = self.api.post_data(item['activity'], item['data'])

        if status == api_status.MISMATCH:
            self.api.get_config()
        
        if (status != api_status.NOT_CONNECTED and status != api_status.NO_SERVICE):
            self.del_rows.append(row_id)
            
    def cleanup(self):
        len(self.del_rows) and self.off_store.rem(self.del_rows, [])

class Storage:
    def __init__(self):
        self.globals = globals.Interface()
        self.off_store = OfflineStore()
        self.realtime_sender = RealtimeSender(self.off_store)
        self.historic_sender = HistoricSender(self.off_store)
        
    def start(self):        
        if self.off_store.start() == False:
            return False
        
        self.realtime_sender.start()
        self.historic_sender.start()
        return True
    
    def push(self, activity, data):
        if self.globals.stop_event.is_set():
            return
        
        if self.realtime_sender.push({'activity': activity, 'data': data}) == False:
            self.off_store.put(activity, data, self.realtime_sender.store_put_callback)
        
    def clear_offline_data(self):
        self.off_store.clr()
        
    def clear_activities(self, activities):
        self.off_store.rem([], activities)

Interface = Storage