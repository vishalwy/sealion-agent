"""
Utility functions and classes.
Implements Utils, Config, ThreadMonitor and notify_terminate
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import json
import re
import threading
import logging
import gc
import sys
import time
import traceback
import exit_status
from constructs import *

_log = logging.getLogger(__name__)  #module wise logging
event_dispatcher = EventDispatcher()  #global event dispatcher instance for cross module communication

def default_termination_hook(message, stack_trace):
    """
    Default hook function called before termination.
    
    Args:
        message: the message to be writen to stderr
        stack_trace: any stack_trace to be writen to stderr
    """
    
    message and sys.stderr.write(message + '\n')
    stack_trace and sys.stderr.write(stack_trace)
    
def notify_terminate(is_gracefull = True, message = '', stack_trace = ''):
    """
    Function called to notify 'terminate' event and terminatehook.
    
    Args:
        is_gracefull: if this is False, it will invoke terminatehook
        message: the message to be writen to stderr
        stack_trace: any stack_trace to be writen to stderr
    """
    
    event_dispatcher.trigger('terminate')  #trigger the event so that modules can cleanup
    is_gracefull == False and terminatehook(message, stack_trace)

terminatehook = default_termination_hook  #terminate hook called for disgraceful shutdown
   
class Utils(Namespace):
    """
    Wrapper for utility functions
    """
    
    @staticmethod
    def sanitize_type(d, schema, is_delete_extra = True, regex = None, is_regex = False, file = None):
        """
        Public static function to cleanup a dict, list or string against a schema given.
        This function works in conjunction with sanitize_dict.
        Together it validates and does cleanup a dict
        
        Args:
            d: item to be sanitized
            schema: the schema defining the rules for the item
            is_delete_extra: delete any extra items found inside the item
            regex: regex to match
            is_regex: is item a regex
            file: filename where the item read from
            
        Returns:
            True on success else False
        """
        
        #get the type name of the item to sanitized and the schema
        d_type_name = type(d).__name__
        schema_type_name = type(schema).__name__

        if d_type_name == 'dict' and schema_type_name == 'dict':  #a dict is delegated to sanitize_dict
            return Utils.sanitize_dict(d, schema, is_delete_extra, file)
        elif d_type_name == 'list' and schema_type_name == 'list':  #if it is a list
            for i in range(0, len(d)):  #sanitize each item in the list
                if Utils.sanitize_type(d[i], schema[0], is_delete_extra, regex, is_regex, file) == False:
                    return False  #failure
                
            return True  #sanitized the list
        elif schema_type_name == 'str':  #if it is a string
            types = schema.split(',')  #a string can be unicode or str, thus we get the types
            flag = False  #flag indicates whether it match with any type given
            
            #match against the types given
            for i in range(0, len(types)):
                if d_type_name == types[i]:
                    flag = True
                    break
                    
            if flag == True:  #matched
                if regex != None and re.match(regex, unicode(d)) == None:  #if regex is given, match the regex
                    return False
                elif (d_type_name == 'str' or d_type_name == 'unicode') and is_regex == True:  #if it is to be considered as a regex, then compile and check
                    try:
                        re.compile(d)
                    except:
                        return False  #failure
                
            return flag
        
        return False

    @staticmethod
    def sanitize_dict(d, schema, is_delete_extra = True, file = None):
        """
        Public static function to cleanup a dict against the schema given.
        This function works in conjunction with sanitize_type.
        Together it validates and does cleanup of a dict
        
        Args:
            d: dict to be sanitized
            schema: the schema defining the rules for the dict
            is_delete_extra: delete any extra items found inside the dict
            file: filename where the dict read from
            
        Returns:
            True on success else False
        """
        
        ret = True  #return value

        #delete any extra keys
        if is_delete_extra == True:
            keys = list(d.keys())
            
            #a '.' as a key schema indicates that it can match with any key.
            #so to avoid the key getting deleted, we are replacing the schema with the a dict made of the key
            if ('.' in schema) and len(schema.keys()) == 1 and len(keys) == 1:
                temp = {}
                temp[keys[0]] = schema['.']
                schema = temp

            #delete extra keys
            for key in keys:
                if key not in schema:
                    file and _log.warn('Ignoring config key \'%s\' in \'%s\' as it is unknown.' % (key, file))
                    del d[key]

        depends_check_keys = []  #keys for which the dependency check to be performed

        for key in schema:  #we have to find a match for every key in schema in the dict
            is_optional = schema[key].get('optional', False)  #is this key optional
            
            if key not in d:  #if the key is not found in dict
                ret = False if is_optional == False else ret  #if it is optional return value remains as it is, else zero
            else:
                if 'depends' in schema[key]:  #collect dependency check keys
                    depends_check_keys.append(key)

                #sanitize the value
                if Utils.sanitize_type(d[key], schema[key]['type'], is_delete_extra, 
                    schema[key].get('regex'), schema[key].get('is_regex', False), file) == False:
                    if file:
                        _log.warn('Ignoring config key \'%s\' in \'%s\' as value is in improper format' % (key, file))
                    else:
                        _log.error('Config key \'%s\' is in improper format' % key)
                        
                    del d[key]
                    ret = False if is_optional == False else ret  #if it is optional return value remains as it is, else zero
                    
        #perform dependency check
        for key in depends_check_keys:
            depends = schema[key]['depends']
            
            for depend in depends:
                if depend not in d:
                    if key in d:
                        file and _log.warn('Ignoring config key \'%s\' in \'%s\' as it failed dependency' % (key, file))
                        del d[key]
                        
                    break

        return ret

    @staticmethod
    def get_safe_path(path):
        """
        Public static function to create path if path does not exists
        
        Args:
            path: path to create.
            
        Returns:
            path
        """
        
        dir = os.path.dirname(path)

        if os.path.isdir(dir) != True:
            os.makedirs(dir)

        return path    
    
    @staticmethod
    def restart_agent(message = '', stack_trace = ''):
        """
        Public static function to restart agent.
        This function replaces the current process with a new executable image.
        
        Args:
            message: any message to log
            stack_trace: any stack trace to log
        """
        
        notify_terminate(False, message, stack_trace)
        _log.info('Restarting agent')
        os.execl(sys.executable, sys.executable, *sys.argv)
     
    @staticmethod
    def get_stack_trace(thread_ident = None):
        """
        Public static function to get the stack trace of threads.
        
        Args:
            thread_ident: thread identifier of the thread for which it should retreive stack trace.
            
        Returns:
            string representing the stack trace.
        """
        
        trace = ''

        #loop throught the sys frames and form the trace
        for thread_id, frame in sys._current_frames().items():
            if thread_ident == None or thread_ident == thread_id:
                trace += '# Thread ID: %s\n' % thread_id if thread_ident == None else ''
                trace += ''.join(traceback.format_list(traceback.extract_stack(frame)))
                trace += '\n\n' if thread_ident == None else ''

        return trace
         
class Config:
    """
    Class abstracs JSON based configuration.
    """
    
    def __init__(self):
        """
        Constructor
        """
        
        self.schema = {}  #schema representing the rules for configuration. subclass should modify this to provide custom rules
        self.file = ''  #filename for this config
        self.data = {}  #dict for config 
        self.lock = threading.RLock()  #thread lock
        
    def __getattr__(self, attr):
        """
        Called when an attribute lookup has not found the attribute in the usual places.
        We use this to provide dat in self.data so that it can be accessed as config_instance.custom_key
        """
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            return self.data[attr]
        except KeyError as e:
            raise AttributeError(unicode(e))
        finally:
            self.lock.release()
        
    def get_dict(self, keys = None, as_dict = True):
        """
        Public method to return filtered dict.
        
        Args:
            keys: keys to return, None indicates all the keys. keys can also be a list of tuples (key, default_value)
            as_dict: whether to return as a dict or DictEx
            
        Returns:
            dict or DictEx depending on as_dict arg
        """
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            return DictEx(self.data).get_dict(keys, as_dict)
        finally:
            self.lock.release()
        
    @staticmethod
    def parse(file, is_data = False):
        """
        Public static function to parse the given file.
        
        Args:
            file: the filename or the dict object to parse
            is_data: True indicates that 'file' should be treated as dict or string, else filename
            
        Returns:
            Returns (dict, True) on success else (dict, False)
        """
        
        value, f, is_parse_failed = {}, None, False

        if is_data == True or os.path.isfile(file) == True:
            try:
                data = file

                #parse the file, based on is_data flag
                if is_data != True:
                    f = open(file, 'r')
                    value = json.load(f)  #read json from file
                elif type(data) is dict:
                    value = data  #data is dict
                else:
                    value = json.loads(data)  #read json from string
            except:
                is_parse_failed = True
            finally:
                f and f.close()

        return (value, is_parse_failed)
        
    def save(self):
        """
        Public method to save the config to file
        
        Returns:
            True on success else False
        """
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        f = None
        
        try:
            #write the config to file in JSON format
            f = open(self.file, 'w')
            json.dump(self.data, f)
            return True
        except:
            return False
        finally:
            f and f.close()
            self.lock.release()
            
    def set(self, data = None):
        """
        Public method to set the config.
        
        Args:
            data: dict containing new config
            
        Returns:
            True on success, an error string on failure
        """
        
        is_data = True  #flag tells whether the data should be interpreted as a file or not
        
        if data == None:  #if no data supplied, load it from the file          
            data = self.file
            is_data = False
            
        config = Config.parse(data, is_data)  #parse the config
        
        #sanitize the config
        if Utils.sanitize_dict(config[0], self.schema, True, self.file if is_data == False else None) == False:
            if is_data == False:
                return '\'%s\' is either missing or corrupted' % self.file
            else:
                return 'Invalid config'
        elif config[1] == True and is_data == False:
            self.file and _log.warn('Ignoring \'%s\' as it is either missing or corrupted' % self.file)
            
        self.lock.acquire()
        self.data.update(config[0])  #update the config
        self.lock.release()
        return True
        
    def update(self, data):
        """
        Public method to update the config.
        
        Args:
            data: dict containing new config
            
        Returns:
            True on success, an error string on failure
        """
        
        config = {}
        self.lock.acquire()
        config.update(self.data)
        self.lock.release()
        config.update(Config.parse(data, True)[0])
        return self.set(config)

class ThreadMonitor(SingletonType('ThreadMonitorMetaClass', (object, ), {})):
    """
    Singleton class to monitor the calling thread for a specified time interval.
    If the thread doesnt repond within the specified timeout, it will restart the agent.
    """
    
    def __init__(self):
        """
        Constructor.
        """
        
        self.registered_threads = {}  #dict of threads registered for monitoring
        self.lock = threading.RLock()  #thread lock
        self.thread = None  #thread instance of the background thread for monitoring other threads
        
    def register(self, timeout = 20, callback = exit_status.AGENT_ERR_RESTART, callback_args = (), callback_kwargs = {}):
        """
        Public method to register the calling thread for monitoring.
        
        Args:
            timeout: timeout in seconds before invoking the callback
            callback: if it is a callable object, invoke it after timeout, restart the agent if it is AGENT_ERR_RESTART, any other number terminate the agent
            callback_args: tuple of arguments for callback
            callback_kwargs: tuple of keyword arguments for callback
            
        Returns:
            True if the thread is registered for monitoring, else False
        """
        
        curr_thread = threading.current_thread()  #get calling thread
        
        if curr_thread == self.thread:  #you cannot monitor the monitoring thread
            return False
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        data = {
            'exp_time': time.time() + timeout, 
            'callback': callback,
            'callback_args': callback_args,
            'callback_kwargs': callback_kwargs
        }
        self.registered_threads['%d' % curr_thread.ident] = data  #register for monitoring
        self.lock.release()
        self.start()  #start the monitoring thread if it is not already
        return True
        
    def unregister(self):
        """
        Public method to unregister the calling thread from monitoring.
        """
        
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            del self.registered_threads['%d' % threading.current_thread().ident]
        except:
            pass
        
        self.lock.release()
        
    def get_expiry_status(self):
        """
        Method to get the exiry status of threads being monitored.
        
        Returns:
            a dict contiaining details of expired thread
        """
        
        ret, temp = {'callback': -1}, {'callback': -1}
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        t = time.time()
        
        for thread_id in self.registered_threads:  #loop through resistered threads
            #form dict for the thread
            data = self.registered_threads[thread_id]
            temp.update(data)
            temp.update({'thread_id': int(thread_id)})
            
            if t > data['exp_time']:  #if the thread expired 
                #form the dict for return value
                ret.update(data)
                ret.update({'thread_id': int(thread_id)})
                
                if ret['callback'] != exit_status.AGENT_ERR_RESTART:  #AGENT_ERR_RESTART has lowest of priority
                    break
                
        #since AGENT_ERR_RESTART has lowest of priority, we try to find another thread asking for terminate
        if (ret['callback'] == exit_status.AGENT_ERR_RESTART and 
            hasattr(temp['callback'], '__call__') == False and temp['callback'] != -1 and temp['callback'] != exit_status.AGENT_ERR_RESTART):
            ret = temp
        
        ret['length'] = len(self.registered_threads)  #return the total number of threads registered
        self.lock.release()
        return ret
    
    def monitor(self):
        """
        Method runs in a new thread.
        """
        
        #if the thread was started without registering any thread for monitoring, then it is intent to run forever
        is_exit_when_empty = False if self.get_expiry_status()['length'] == 0 else True
        
        while 1:
            time.sleep(10)
            ret = self.get_expiry_status()
           
            if is_exit_when_empty == True and ret['length'] == 0:  #terminate?
                break

            if hasattr(ret['callback'], '__call__'):  #a callabcle object
                ret['callback'](*ret['callback_args'], **ret['callback_kwargs'])
            elif ret['callback'] == exit_status.AGENT_ERR_RESTART:  #restart agent
               Utils.restart_agent('Thread %d is not responding' % ret['thread_id'], Utils.get_stack_trace(ret['thread_id']))
            elif ret['callback'] != -1:  #some thread expired and asked to terminate agent
                notify_terminate(False, 'Thread %d is not responding' % ret['thread_id'], Utils.get_stack_trace(ret['thread_id']))
                _log.info('Agent terminating with status code %d' % ret['callback'])
                os._exit(ret['callback'])
               
        self.thread = None
        
    def start(self):
        """
        Public method to start the monitoring thread.
        """
        
        if self.thread != None:  #if it is already running
            return
        
        self.thread = ThreadEx(target = self.monitor, name = 'ThreadMonitor')
        self.thread.daemon = True
        self.thread.start()
