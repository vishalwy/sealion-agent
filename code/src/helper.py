import os
import json
import re
import threading
import logging
from constructs import *

_log = logging.getLogger(__name__)
   
class Utils(Namespace):
    @staticmethod
    def sanitize_type(d, schema, is_delete_extra = True, regex = None, is_regex = False, file = None):
        d_type_name = type(d).__name__
        schema_type_name = type(schema).__name__

        if d_type_name == 'dict' and schema_type_name == 'dict':
            return Utils.sanitize_dict(d, schema, is_delete_extra, file)
        elif d_type_name == 'list' and schema_type_name == 'list':
            for i in range(0, len(d)):
                if Utils.sanitize_type(d[i], schema[0], is_delete_extra, regex, file) == False:
                    return False
                
            return True
        elif schema_type_name == 'str':
            types = schema.split(',')
            flag = False
            
            for i in range(0, len(types)):
                if d_type_name == types[i]:
                    flag = True
                    break
                    
            if flag == True and (d_type_name == 'str' or d_type_name == 'unicode'):
                if regex != None and re.match(regex, d) == None:
                    return False
                elif is_regex == True:
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
                    file and _log.warn('Ignoring config key "%s" in %s; unknown key' % (keys[i], file))
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
                    file and _log.warn('Ignoring config key "%s" in %s; value in improper format' % (key, file))
                    del d[key]
                    ret = 0 if is_optional == False else ret                

        for j in range(0, len(depends_check_keys)):
            depends = schema[depends_check_keys[j]]['depends']

            for i in range(0, len(depends)):
                if (depends[i] in d) == False:
                    if (depends_check_keys[j]) in d:
                        file and _log.warn('Ignoring config key "%s" in %s; failed dependency' % (depends_check_keys[j], file))
                        del d[depends_check_keys[j]]
                        
                    break

        return False if ret == 0 else True

    @staticmethod
    def get_safe_path(path):
        dir = os.path.dirname(path)

        if os.path.isdir(dir) != True:
            os.makedirs(dir)

        return path    
         
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
        value, f = {}, None

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
                pass
            finally:
                f and f.close()

        return value
        
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
        
        if Utils.sanitize_dict(config, self.schema, True, self.file if is_data == False else None) == False:
            if is_data == False:
                return self.file + ' is either missing or currupted'
            else:
                return 'Invalid config'
            
        self.lock.acquire()
        self.data = config
        self.lock.release()
        return True
        
    def update(self, data):
        config = {}
        self.lock.acquire()
        config.update(self.data)
        self.lock.release()
        config.update(Config.parse(data, True))
        return self.set(config)