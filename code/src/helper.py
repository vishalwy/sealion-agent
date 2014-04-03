__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import json
import re
import threading
import logging
import subprocess
import sys
import time
import traceback
import exit_status
from constructs import *

_log = logging.getLogger(__name__)
event_dispatcher = EventDispatcher()
   
class Utils(Namespace):
    @staticmethod
    def sanitize_type(d, schema, is_delete_extra = True, regex = None, is_regex = False, file = None):
        d_type_name = type(d).__name__
        schema_type_name = type(schema).__name__

        if d_type_name == 'dict' and schema_type_name == 'dict':
            return Utils.sanitize_dict(d, schema, is_delete_extra, file)
        elif d_type_name == 'list' and schema_type_name == 'list':
            for i in range(0, len(d)):
                if Utils.sanitize_type(d[i], schema[0], is_delete_extra, regex, is_regex, file) == False:
                    return False
                
            return True
        elif schema_type_name == 'str':
            types = schema.split(',')
            flag = False
            
            for i in range(0, len(types)):
                if d_type_name == types[i]:
                    flag = True
                    break
                    
            if flag == True:
                if regex != None and re.match(regex, str(d)) == None:
                    return False
                elif (d_type_name == 'str' or d_type_name == 'unicode') and is_regex == True:
                    try:
                        re.compile(d)
                    except:
                        return False
                
            return flag
        
        return False

    @staticmethod
    def sanitize_dict(d, schema, is_delete_extra = True, file = None):
        ret = 1

        if is_delete_extra == True:  
            keys = list(d.keys())
            
            if ('.' in schema) and len(schema.keys()) == 1 and len(keys) == 1:
                temp = {}
                temp[keys[0]] = schema['.']
                schema = temp

            for i in range(0, len(keys)):
                if (keys[i] in schema) == False:
                    file and _log.warn('Ignoring config key "%s" in %s as it is unknown.' % (keys[i], file))
                    del d[keys[i]]
                    continue

        depends_check_keys = []

        for key in schema:
            is_optional = schema[key].get('optional', False)
            
            if (key in d) == False:
                ret = 0 if is_optional == False else ret
            else:
                if ('depends' in schema[key]) == True:
                    depends_check_keys.append(key)

                if Utils.sanitize_type(d[key], schema[key]['type'], is_delete_extra, 
                                        schema[key].get('regex'), schema[key].get('is_regex', False), file) == False:
                    if file:
                        _log.warn('Ignoring config key "%s" in %s as value is in improper format' % (key, file))
                    else:
                        _log.error('Config key "%s" is in improper format' % key)
                        
                    del d[key]
                    ret = 0 if is_optional == False else ret                

        for j in range(0, len(depends_check_keys)):
            depends = schema[depends_check_keys[j]]['depends']

            for i in range(0, len(depends)):
                if (depends[i] in d) == False:
                    if (depends_check_keys[j]) in d:
                        file and _log.warn('Ignoring config key "%s" in %s as it failed dependency' % (depends_check_keys[j], file))
                        del d[depends_check_keys[j]]
                        
                    break

        return False if ret == 0 else True

    @staticmethod
    def get_safe_path(path):
        dir = os.path.dirname(path)

        if os.path.isdir(dir) != True:
            os.makedirs(dir)

        return path    
    
    @staticmethod
    def restart_agent(message = '', stack_trace = ''):
        timeout = 10
        message = message + '. ' if message else ''
        message += 'Restarting agent in %d seconds.' % timeout
        _log.info(message)
        subprocess.Popen(['bash', '-c', 'sleep %d ; "%s" %s' % (timeout, sys.executable, ' '.join(['"%s"' % arg for arg in sys.argv]))])
        event_dispatcher.trigger('terminate', exit_status.AGENT_ERR_RESTART, stack_trace)
        os._exit(exit_status.AGENT_ERR_RESTART)
     
    @staticmethod
    def get_stack_trace(thread_ident = None):
        trace = ''

        for thread_id, frame in sys._current_frames().items():
            if thread_ident == None or thread_ident == thread_id:
                trace += '# Thread ID: %s\n' % thread_id if thread_ident == None else ''
                trace += ''.join(traceback.format_list(traceback.extract_stack(frame)))
                trace += '\n\n' if thread_ident == None else ''

        return trace
         
class Config:
    def __init__(self):
        self.schema = {}
        self.file = ''
        self.data = {}
        self.lock = threading.RLock()
        
    def __getattr__(self, attr):
        self.lock.acquire()
        
        try:
            return self.data[attr]
        except KeyError as e:
            raise AttributeError(str(e))
        finally:
            self.lock.release()
        
    def get_dict(self, keys = None, as_dict = True):
        self.lock.acquire()
        
        try:
            return DictEx(self.data).get_dict(keys, as_dict)
        finally:
            self.lock.release()
        
    @staticmethod
    def parse(file, is_data = False):
        value, f, is_parse_failed = {}, None, False

        if is_data == True or os.path.isfile(file) == True:        
            try:
                data = file

                if is_data != True:
                    f = open(file, 'r')
                    value = json.load(f)
                elif type(data) is dict:
                    value = data
                else:
                    value = json.loads(data)
            except:
                is_parse_failed = True
            finally:
                f and f.close()

        return (value, is_parse_failed)
        
    def save(self):
        self.lock.acquire()
        f = None
        
        try:
            f = open(self.file, 'w')
            json.dump(self.data, f)
            return True
        except:
            return False
        finally:
            f and f.close()
            self.lock.release()
            
    def set(self, data = None):
        is_data = True
        
        if data == None:            
            data = self.file
            is_data = False
            
        config = Config.parse(data, is_data)
        
        if Utils.sanitize_dict(config[0], self.schema, True, self.file if is_data == False else None) == False:
            if is_data == False:
                return self.file + ' is either missing or corrupted'
            else:
                return 'Invalid config'
        elif config[1] == True and is_data == False:
            self.file and _log.warn('Ignoring %s as it is either missing or corrupted' % self.file)
            
        self.lock.acquire()
        self.data = config[0]
        self.lock.release()
        return True
        
    def update(self, data):
        config = {}
        self.lock.acquire()
        config.update(self.data)
        self.lock.release()
        config.update(Config.parse(data, True)[0])
        return self.set(config)

class ThreadMonitor(SingletonType('ThreadMonitorMetaClass', (ThreadEx, ), {})):
    def __init__(self):
        ThreadEx.__init__(self)
        self.registered_threads = {}
        self.lock = threading.RLock()
        self.daemon = True
        
    def register(self, terminate_status = exit_status.AGENT_ERR_RESTART, timeout = 20):
        self.lock.acquire()
        thread_id = threading.current_thread().ident
        data = {
            'exp_time': time.time() + timeout, 
            'terminate_status': terminate_status,
            'thread_id': thread_id
        }
        self.registered_threads['%d' % thread_id] = data
        self.lock.release()
        
    def unregister(self):
        self.lock.acquire()
        
        try:
            del self.registered_threads['%d' % threading.current_thread().ident]
        except:
            pass
        
        self.lock.release()
        
    def get_expiry_status(self):
        ret = (-1, 0)
        self.lock.acquire()
        t = time.time()
        
        for thread in self.registered_threads:
            if thread['exp_time'] > t:
                ret = (thread['terminate_status'], thread['thread_id'])
                
                if ret[0] != exit_status.AGENT_ERR_RESTART:
                    break
                    
        self.lock.release()
        return ret
    
    def exe(self):
        while 1:
            time.sleep(10)
            ret = self.get_expiry_status()
            
            if ret[0] == exit_status.AGENT_ERR_RESTART:
                Utils.restart_agent('Thread %d is not responding' % ret[1], Utils.get_stack_trace(ret[1]))
            elif ret[0] != -1:
                _log.info('Thread %d is not responding. Agent terminating with status code %d.' % (ret[1], ret[0]))
                event_dispatcher.trigger('terminate', ret[0], Utils.get_stack_trace(ret[1]))
                os._exit(ret[0])
        
    