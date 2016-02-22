"""
Abstracts the online and offline storage mechanism.
This module implements OfflineStore, Sender, RealtimeSender, HistoricSender and Storage classes
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import threading
import time
import json
import sqlite3
import helper
import universal
import api
from constructs import *

_log = logging.getLogger(__name__)  #module level logging

class OfflineStore(ThreadEx):    
    """
    Implements offline data store. 
    Used as an interface for sqlite3 module to store data to disk if the network is not available or the internal queue is full.
    """
    
    def __init__(self):
        """
        Constructor.
        """
        
        ThreadEx.__init__(self)  #initialize base class
        self.univ = universal.Universal()  #save a reference to Universal for optimized access
        self.db_file = self.univ.db_path  #sqlite db file path; same property is used as absolute path to the filename once offline store is started
        self.conn = None  #sqlite db connection;
        self.conn_event = threading.Event()  #event to synchronize connection made in the thread
        self.task_queue = queue.Queue()  #the task queue used to feed the operations to thread
        self.is_bulk_insert = False  #whether to use transaction around contigous insert statements
        self.pending_insert_row_count = 0  #number of rows pending to be inserted in a transaction
        self.select_max_timestamp = int(time.time() * 1000)  #timestamp limit for retreival of rows
        self.select_timestamp_lock = threading.RLock()  #thread lock for updating timestamp limit for retreival of rows
        
    def start(self):
        """
        Public method to start the offline store. This in turn starts a thread for sqlite operations.
        
        Returns:
            True on success else False
        """
        
        self.db_file = helper.Utils.get_safe_path(self.db_file + ('/%s.db' % self.univ.config.agent.get(['config', 'org']))) #form absolute path to db filename
        ThreadEx.start(self) #start the thread
        self.conn_event.wait() #synchronize connection           
        return True if self.conn else False
    
    def stop(self):
        """
        Public method to stop the store. 
        This pushes 'close' task in the queue and thus it might take some time to execute depending on the number of items in the queue.
        """
        
        self.task_queue.put({'op': 'close', 'kwargs': {}})
        
    def put(self, activity, data, callback = None):
        """
        Public method to insert data in store. 
        This pushes 'insert' task in the queue and thus it might take some time to execute depending on the number of items in the queue.
        
        Args:
            activity: activity id of the data to be inserted
            data: dict containing the data to be inserted
            callback: a callable object which is called after the operation is completed
        """
        
        self.task_queue.put({'op': 'insert', 'kwargs': {'activity': activity, 'data': data, 'callback': callback}})
        
    def put_bulk(self, rows):
        """
        Public method to insert rows in a single transaction. 
        This pushes 'insert_bulk' task in the queue and thus it might take some time to execute depending on the number of items in the queue.
        
        Args:
            rows: dict containing activity id and the data to be inserted
        """
        
        self.task_queue.put({'op': 'insert_bulk', 'kwargs': {'rows': rows}})
        
    def get(self, limit, callback):
        """
        Public method to select rows. 
        This pushes 'select' task in the queue and thus it might take some time to execute depending on the number of items in the queue.
        
        Args:
            limit: max number of rows to retreive
            callback: a callable object which is called after the operation is completed
        """
        
        self.task_queue.put({'op': 'select', 'kwargs': {'limit': limit, 'callback': callback}})
        
    def rem(self, row_ids, activities):
        """
        Public method to delete rows. 
        This pushes 'insert_bulk' task in the queue and thus it might take some time to execute depending on the number of items in the queue.
        
        Args:
            row_ids: list of sqlite row ids to be deleted
            activities: list of activity ids to be deleted
        """
        
        self.task_queue.put({'op': 'delete', 'kwargs': {'row_ids': row_ids, 'activities': activities}})
        
    def clr(self, exclude_activities = []):
        """
        Public method to truncate the table. 
        This pushes 'truncate' task in the queue and thus it might take some time to execute depending on the number of items in the queue.
        
        Args:
            exclude_activities: list of activity ids to be excluded from deletion
        """
        
        self.task_queue.put({'op': 'truncate', 'kwargs': {'exclude_activities': exclude_activities}})
        
    def set_bulk_insert(self, is_bulk_insert):
        """
        Public method to enable bulk insert flag. 
        When bulk insert is enabled, it automatically puts all the insert operations in a transaction until an operation other than insert appears.
        """
        
        self.is_bulk_insert = is_bulk_insert
        
    @property
    def select_timestamp(self):
        """
        Property to get the timestamp limit for selecting rows. 
        
        Returns:
            Timestamp limit for selecting rows
        """
        
        self.select_timestamp_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        timestamp = self.select_max_timestamp
        self.select_timestamp_lock.release()    
        return timestamp
    
    @select_timestamp.setter
    def select_timestamp(self, timestamp):
        """
        Property to set the timestamp limit for selecting rows. 
        """
        
        self.select_timestamp_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        self.select_max_timestamp = timestamp
        self.select_timestamp_lock.release()
        
    def exe(self):
        """
        Method that runs in the new thread.
        """
        
        try:
            self.conn = sqlite3.connect(self.db_file)  #connect to the sqlite db file
            _log.debug('Created %s at \'%s\'' % (self.name, self.db_file))
        except Exception as e:
            _log.error('Failed to create %s at \'%s\'; %s' % (self.name, self.db_file, unicode(e)))
            self.conn_event.set()  #set the event so that self.start can continue
            return
            
        self.cursor = self.conn.cursor()  #save connection cursor for optimize the access
        
        if self.setup_schema() == False:  #try to setup the schema
            _log.error('Failed to create schema in %s at \'%s\'' % (self.name, self.db_file))
            self.close_db()  #close the db file and any resources opened
            self.conn_event.set()  #set the event so that self.start can continue
            return
        
        self.conn_event.set()  #set the event so that self.start can continue
        
        while 1:  #process the tasks
            task = self.task_queue.get()  #get the task from queue. this is a blocking wait
            
            if self.perform_task(task) == False:  #perform the task received, a 'close' task will return False
                break
        
    def perform_task(self, task):
        """
        Method to perform the the task given.
        
        Args:
            task: the operation to be carried out. task should be the name of a method of this class
            
        Returns:
            False if task is 'close' else True
        """
        
        is_bulk_insert = False  #use the flag to identify bulk insert operation
            
        if self.is_bulk_insert == True:
            if task['op'] == 'insert':  #convert a normal insert into a bulk insert
                getattr(self, 'insert_bulk')(**{'rows': [{'activity': task['kwargs']['activity'], 'data': task['kwargs']['activity']}], 'is_commit': False})
                is_bulk_insert = True
            elif task['op'] == 'insert_bulk':
                getattr(self, 'insert_bulk')(**{'rows': task['kwargs']['rows'], 'is_commit': False})
                is_bulk_insert = True
                
        if is_bulk_insert == False:  #if it is not a bulk insert then we need to commit any pending transaction before performing the task
            self.pending_insert_row_count and getattr(self, 'insert_bulk')(**{'rows': []})  #an empty list will do the trick as the default mode is to commit immediately
            self.pending_insert_row_count = 0  #no more pending transaction
        else:
            return True  #added row to transaction

        return getattr(self, task['op'])(**task['kwargs']) #carry out the actual operation
        
    def setup_schema(self):
        """
        Method to setup/validate the schema for the table.
        
        Returns:
            True on success else False
        """
        
        #schema as returned by PRAGMA TABLE_INFO; (index, col_name, col_type, not_null, default, pk)
        schema = [
            (0, 'activity', 'VARCHAR(50)', 1, None, 1),
            (1, 'timestamp', 'INT', 1, None, 1), 
            (2, 'return_code', 'INT', 1, None, 0), 
            (3, 'output', 'BLOB', 1, None, 0),
            (4, 'metrics', 'BLOB', 0, None, 0)
        ]
        
        try:
            self.cursor.execute('PRAGMA TABLE_INFO(data)')
            orig_schema = set([col[:3] + (1 if col[-1] else 0,) for col in schema])
            curr_schema = set([col[:3] + (1 if col[-1] else 0,) for col in self.cursor.fetchall()])

            #if there is a schema mismatch, drop the table and raise an exception so that we recreate it
            if len(orig_schema - curr_schema) > 0 or len(curr_schema - orig_schema) > 0:  
                self.cursor.execute('DROP TABLE data')
                raise Exception()
        except:    
            try:
                columns, pk = '', ''

                for col in schema:  #frame the columns and pk for create table statement
                    not_null = 'NOT NULL' if col[3] == 1 else 'NULL'
                    default = '' if col[4] == None else col[4]
                    columns += '%s%s %s %s %s' % (', ' if columns else '', col[1], col[2], not_null, default)
                    pk += (', ' if pk else '') + col[1] if col[5] == 1 else ''

                pk = (', PRIMARY KEY(%s)' % pk) if pk else ''  #pk clause
                query = 'CREATE TABLE data(%s%s)' % (columns, pk)  #actual create table statement
                self.cursor.execute(query)
            except:
                return False
            
        return True
    
    def perform_insert(self, activity, data):
        """
        Helper method to perform insert.
        
        Args:
            activity: activity id for the data
            data: dict containing the data
        """
        
        Storage.get_data(data)  #get the data. read the get_data doc to know why this is required
        metrics, values = data.get('metrics'), '?, ?, ?, ?, ?'
        
        #we have to convert output and metrics to string, as it can be a dict
        args = (activity, data['timestamp'], data['returnCode'], json.dumps(data['data']), json.dumps(metrics) if metrics else None)
        self.cursor.execute('INSERT INTO data VALUES(%s)' % values, args)
    
    def insert(self, activity, data, callback = None):
        """
        Method to insert data in sqlite db
        
        Args:
            activity: activity id for the data
            data: dict containing data
            callback: a callable object which is called after successful insert
            
        Returns:
            True
        """
        
        try:
            self.perform_insert(activity, data)
            self.conn.commit()  #commit the changes
            _log.debug('Inserted %s to %s' % (helper.format_job(activity, data['timestamp']), self.name))
            callback and callback()  #callback for successful insertion
        except Exception as e:
            _log.error('Failed to insert row to %s; %s' % (self.name, unicode(e)))
        
        return True
    
    def insert_bulk(self, rows, is_commit = True):        
        """
        Method to insert rows in a transaction to sqlite db
        
        Args:
            rows: list of dicts containing activity id and the data to be inserted
            is_commit: whether to commit the transaction
            
        Returns:
            True
        """
        
        try:
            for row in rows:
                self.perform_insert(row['activity'], row['data'])
                self.pending_insert_row_count += self.cursor.rowcount  #increment the count of pending rows to be committed
                
            if is_commit == False:
                return True  #we dont want to commit now
        
            self.conn.commit()
            _log.debug('Inserted %d rows to %s' % (self.pending_insert_row_count, self.name))
        except Exception as e:
            _log.error('Failed to insert rows to %s; %s' % (self.name, unicode(e)))
        
        return True
    
    def select(self, limit, callback):      
        """
        Method to select rows from sqlite db.
        
        Args:
            limit: the number of rows to be retreived
            callback: a callable object; callback(rows, total_rows) that will be called after the query returns
            
        Returns:
            True
        """
        
        try:
            rows = []
            self.cursor.execute('SELECT ROWID, * FROM data WHERE timestamp <= %d ORDER BY timestamp LIMIT %d' % (self.select_timestamp, limit))
            
            while 1:  #fetch rows one by one
                row = self.cursor.fetchone()
                
                if not row:
                    break
                    
                #try to extract the metrics
                try:
                    metrics = json.loads(row[5])
                except:
                    metrics = None
                    
                try:
                    #we have to convert row[4] from string, as it can be a dict representation
                    row = (row[0], row[1], row[2], row[3], json.loads(row[4]), metrics)
                except:
                    #backward compatiblity for agent version < 3.1.0 as the string was written without escaping
                    row = (row[0], row[1], row[2], row[3], row[4], metrics)
                    
                rows.append(row)
                
            self.cursor.execute('SELECT COUNT(*) FROM data')
            total_rows = self.cursor.fetchone()[0]  #get the total number of rows
        except Exception as e:
            _log.error('Failed to retreive rows from %s; %s' % (self.name, unicode(e)))
            return True
        
        _log.debug('Retreived %d out of %d rows from %s' % (len(rows), total_rows, self.name))
        callback(rows, total_rows)  #callback serve the rows
        return True
            
    def delete(self, row_ids = [], activities = []):
        """
        Method to delete rows from sqlite db.
        
        Args:
            row_ids: list of sqlite row ids to be deleted
            activities: list of activity ids to be deleted
            
        Returns:
            True
        """
        
        try:
            format = (','.join('?' * len(row_ids)), ','.join('?' * len(activities)))  #format string containing as many '?' as required
            self.cursor.execute('DELETE FROM data WHERE ROWID IN (%s) OR activity IN (%s)' % format, row_ids + activities)
            self.conn.commit()  #commit the changes
            _log.debug('Deleted %d records from %s' % (self.cursor.rowcount, self.name))
        except Exception as e:
            _log.error('Failed to delete rows from %s; %s' % (self.name, unicode(e)))
        
        return True
    
    def truncate(self, exclude_activities = []):
        """
        Method to truncate rows from sqlite db.
        
        Args:
            exclude_activities: list of activity ids to be excluded from deletion
            
        Returns:
            True
        """
        
        try:
            self.cursor.execute('DELETE FROM data WHERE activity NOT IN (%s)' % ','.join('?' * len(exclude_activities)), exclude_activities)
            self.conn.commit()
            _log.debug('Deleted %d records from %s' % (self.cursor.rowcount, self.name))
        except Exception as e:
            _log.error('Failed to delete rows from %s; %s' % (self.name, unicode(e)))
        
        return True
    
    def close_db(self):
        """
        Method to close sqlite db.
        """
        
        _log.debug('Closing %s at \'%s\'' % (self.name, self.db_file))
        self.conn.close()
        self.conn = None
    
    def close(self):
        """
        Method to perform cleanup and close the db.
            
        Returns:
            False
        """
        
        _log.debug('%s received stop event' % self.name)
        _log.debug('%s cleaning up task queue' % self.name)
        
        while 1:  #fetch all the tasks in the task queue
            try:
                task = self.task_queue.get(False)  #get the task; non blocking
                
                if task['op'] != 'select' and task['op'] != 'close':  #ignore any 'select' or 'close' tasks already in the queue
                    self.perform_task(task)
            except:
                break

        self.close_db()  #close db
        return False
   
class Sender(ThreadEx):   
    """
    Base class that implements sending data using api module.
    """
    
    off_store_lock = threading.RLock()  #store lock to synchronize access to offline store
    store_data_available = True  #whether we have data available in offline store
    validate_funct = None  #the function that validates the activity before processing
    
    def __init__(self, off_store):
        """
        Constructor.
        
        Args:
            off_store: offline store instance
        """
        
        ThreadEx.__init__(self)  #initialize base class
        self.univ = universal.Universal()  #save a reference to Universal for optimized access
        self.off_store = off_store  #offline store instance to be used
        self.queue_max_size = 150  #max sending queue count
        self.ping_interval = 10  #the ping interval for retry after an failed api request
        self.queue = queue.Queue(self.queue_max_size)  #sending queue
        self.last_ping_time = int(time.time())  #saves the last time api was pinged
        
    def push(self, item):
        """
        Method to put the data in the sender queue.
        A side effect of this method is that it pings the api session if time delta exceeds ping interval.
        
        Args:
            item: item to be inserted in the sending queue
            
        Returns:
            True on success else False
        """
        
        try:
            self.queue.put(item, False)  #try to put the item, non blocking
        except:
            return False  #failed to put the item
        finally:
            t = int(time.time())
        
            if self.last_ping_time - t > self.ping_interval:  #ping api session if the time delta exceeds ping interval
                self.last_ping_time = t
                api.session.ping()
        
        return True
        
    def wait(self):
        """
        Method waits for post event a minimum of ping interval seconds. The idea is to wait for some time after a failed api request.
        For an unauthorized api session, the function blocks forever.
        
        Returns:
            False if it finds that the global stop event is set, else True
        """
        
        if self.univ.post_event.is_set() == False:  #if post event is not set
            timeout = self.ping_interval if api.session.is_authenticated() else None  #for unauthorized api session the wait timeout is None, indicating a blocking wait forever
            _log.debug('%s waiting for post event%s' % (self.name, ' for %d seconds' % timeout if timeout else ''))
            self.univ.post_event.wait(timeout)
        
        if self.univ.stop_event.is_set() == True:  #we need to stop now
            _log.debug('%s received stop event' % self.name)
            return False
        
        return True
    
    @staticmethod
    def store_put_callback():
        """
        Static function to mark the offline store as available.
        This function is used as callback from offline store's insert method
        """
        
        Sender.store_available(True)
            
    @staticmethod
    def store_available(is_available = None):
        """
        Static function to get/set store availability
        
        Args:
            is_available: True if data available, False if not available, None to retreive the availability
            
        Returns:
            True if data available else False
        """
        
        Sender.off_store_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        if is_available == None:
            is_available = Sender.store_data_available  #retreive status
        else:
            if is_available == True and Sender.store_data_available == False:  #set status as available
                _log.debug('Marking OfflineStore as available')
                Sender.store_data_available = True
            elif is_available == False and Sender.store_data_available == True:  #set status as not available
                _log.debug('Marking OfflineStore as not available')
                Sender.store_data_available = False
            
        Sender.off_store_lock.release()
        return is_available
        
    def exe(self):       
        """
        Method that runs in the new thread.
        """
        
        while 1:
            if self.wait() == False:  #wait for the events
                break
                
            try:
                item = self.queue.get(True, 5)  #get the item from sending queue, blocks for a max of 5 seconds
                
                if Sender.validate_funct(item['activity']) == None:  #validate the activity, it might be possible that we are trying to send an non permitted activity 
                    _log.debug('Discarding activity %s' % item['activity'])                    
                    continue
            except:               
                self.queue_empty()  #carry out any additional operations on queue empty
                continue
                
            self.post_data(item)  #post the data 
                
        self.cleanup()  #perform any cleanup
    
    def queue_empty(self):
        """
        Method that is called when the sending queue is empty.
        Dervied class should implement this to perform additional operations.
        """
        
        pass
    
    def cleanup(self):
        """
        Method that is called before the thread exits.
        Dervied class should implement this to perform additional operations.
        """
        
        pass
    
    def post_data(self, item):
        """
        Method to post the data.
        Dervied class should implement this to post the data.
        
        Args:
            item: item to be sent
        """
        
        pass
            
class RealtimeSender(Sender): 
    """
    Implements real time sending of data as the activities are executed.
    """
    
    def post_data(self, item):
        """
        Method to post the data.
        
        Args:
            item: item to be sent
        """
        
        Storage.get_data(item['data'])  #get the data. read get_data doc to know why this is required
        
        #update the timestamp limit for selecting rows to the last real time data retreived.
        #this will prevent any data sent to offline store due to queue overflow being sent before real time queue clears up
        self.off_store.select_timestamp = item['data']['timestamp']
        
        status = api.session.post_data(item['activity'], item['data'])

        if status == api.Status.MISMATCH:  #a mismatch status indicates that we missed a config update event, so we are doing it now
            api.session.get_config()
        elif api.is_not_connected(status) == True or status == api.Status.UNAUTHORIZED:  #save to offline store if the api session is not connected or unauthorized
            self.off_store.put(item['activity'], item['data'], Sender.store_put_callback)
            
    def queue_empty(self):
        """
        Method that is called when the sending queue is empty.
        The method updates the timestamp limit for selecting rows.
        """
        
        #update the timestamp limit for selecting rows to the current timestamp.
        #this will start sending any data stored already in offline store
        self.off_store.select_timestamp = int(time.time() * 1000)
            
    def cleanup(self):
        """
        Method that is called before the thread exits.
        This method cleans up the items in the queue and puts it into offline store.
        """
        
        _log.debug('%s cleaning up queue' % self.name)
        self.off_store.set_bulk_insert(True)  #enable bulk insert so that the queue is cleaned up quickly
        rows = []
            
        while 1:
            try:
                rows.append(self.queue.get(False))
            except:
                break
                
        len(rows) and self.off_store.put_bulk(rows)  #bulk insert any rows
        self.off_store.stop()  #signal offline store to stop
    
class HistoricSender(Sender):
    """
    Implements sending offline data available in sqlite as a result of real time sender queue overflow, or network failure.
    """
    
    def __init__(self, off_store):
        """
        Constructor.
        
        Args:
            off_store: offline store instance
        """
        
        Sender.__init__(self, off_store)  #initialize base class
        self.del_rows = []  #keeps the sqlite row_ids of deleted rows
        self.queue_max_size = 20  #maximum size of the sending queue
        
    def queue_empty(self):
        """
        Method that is called when the sending queue is empty.
        """
        
        if len(self.del_rows):  #if we have any rows to delete from sqlite
            self.off_store.rem(self.del_rows, [])
            self.del_rows = []  #no more rows to delete
        
        if Sender.store_available():  #get the rows into the queue if we have rows available in offline store
            self.off_store.get(self.queue_max_size, self.store_get_callback)
        
    def store_get_callback(self, rows, total_rows):
        """
        A callback method used to retreive the rows from the offline store.
        
        Args:
            rows: list of tuples representing a row in sqlite table
            total_rows: total number of rows available in sqlite table
        """
        
        row_count, i = len(rows), 0
        
        while i < row_count:  #push all the rows retreived into the sending queue          
            data = {
                'timestamp': rows[i][2],
                'returnCode': rows[i][3],
                'data': rows[i][4]
            }
            
            if rows[i][5]:
                data['metrics'] = rows[i][5]
            
            if self.push({'row_id': rows[i][0], 'activity': rows[i][1], 'data': data}) == False:  #push rows to the sending queue until it fails
                break
                
            i += 1
        
        _log.debug('Pushed %d rows to %s from %s' % (i, self.name, self.off_store.__class__.__name__))
        Sender.store_available(i != total_rows)  #update the store availability
        
    def post_data(self, item):
        """
        Method to post the data.
        
        Args:
            item: item to be sent
        """
        
        row_id = item.get('row_id')  #sqlite row_id used to delete the row once it has been sent
        status = api.session.post_data(item['activity'], item['data'])

        if status == api.Status.MISMATCH:  #a mismatch status indicates that we missed a config update event, so we are doing it now
            api.session.get_config()
        
        #delete from offline store if data was sent; we consider it is sent if api session is connected and is not unauthorized.
        #no need to check for any other status code.
        if api.is_not_connected(status) == False and status != api.Status.UNAUTHORIZED:
            self.del_rows.append(row_id)
        else:
            Sender.store_available(True)  #if sending failed, we need to mark offline store as available
            
    def cleanup(self):
        """
        Method that is called before the thread exits.
        This method deletes any rows from sqlite.
        """
        
        _log.debug('%s cleaning up deleted rows' % self.name)
        len(self.del_rows) and self.off_store.rem(self.del_rows, [])

class Storage:
    """
    Abstracts OfflineStore, RealtimeSender and HistoricSender and provides public methods to operate on them
    """
    
    def __init__(self):
        """
        Constructor.
        """
        
        self.univ = universal.Universal()  #save a reference to Universal for optimized access
        self.off_store = OfflineStore()  #offline store
        self.realtime_sender = RealtimeSender(self.off_store)  #real time sender
        self.historic_sender = HistoricSender(self.off_store)  #historic sender
        
    @staticmethod
    def get_data(data):
        """
        Public static function to convert the data['data'] on demand.
        It makes a function call if data['data'] is a callable object to get data, else it directly uses the object.
        Read Job.get_data to know why this wrapper is required.
        
        Args:
            data: a dict whose key 'data' to be converted.
            
        Returns:
            The dict passed to the function whose 'data' key is converted.
        """       

        data['data'], metrics = data['data']() if hasattr(data['data'], '__call__') else (data['data'], None)
        
        if metrics:
            data['metrics'] = metrics
        
        return data
        
    def start(self):        
        """
        Public method to start offline store and the two sender instances
        """
        
        if self.off_store.start() == False:  #cannot start offline store
            return False
        
        #trigger an event and some other module respond to the event with function used to validate activities
        self.univ.event_dispatcher.trigger('get_activity_funct', lambda x: [True, setattr(Sender, 'validate_funct', x)][0])
        
        #start senders
        self.realtime_sender.start()
        self.historic_sender.start()
        return True
    
    def push(self, activity, data):
        """
        Public method to push the data for sending.
        The method first attempts to push it in real time sender queue, on failure it puts it in offline store.
        
        Args:
            activity: activity id of the data
            data: data to send
        """
        
        #return if we need to stop or no data to be pushed
        if not data or self.univ.stop_event.is_set():
            return
        
        if self.realtime_sender.push({'activity': activity, 'data': data}) == False:  #try to push data to real time sender
            self.off_store.put(activity, data, Sender.store_put_callback)  #on failure push it to sqlite table
        
    def clear_offline_data(self, exclude_activities = []):
        """
        Public method to clear sqlite table.
        
        Args:
            exclude_activities: activity ids to be exclued from deletion
        """
        
        self.off_store.clr(exclude_activities)

