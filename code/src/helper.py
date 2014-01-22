import os
import sys
import json
import re
from lib import requests
import pdb

class EmptyClass:
    pass

class SingletonType(type):
    def __call__(cls, *args, **kwargs):
        if hasattr(cls, '__instance') == False:
            setattr(cls, '__instance', super(SingletonType, cls).__call__(*args, **kwargs))
        elif cls is not getattr(getattr(cls, '__instance'), '__class__'):
            setattr(cls, '__instance', super(SingletonType, cls).__call__(*args, **kwargs))
            
        return getattr(cls, '__instance')
    
class Namespace:    
    def __init__(self):
        raise RuntimeError, 'Cannot instantiate class'
    
class Utils(Namespace):
    @staticmethod
    def is_success(response):
        return True if (response.status_code == 304 or (response.status_code >= 200 and response.status_code < 300)) else False

    @staticmethod
    def sanitize_type(d, schema, is_delete_extra = True):
        type_name = type(d).__name__

        if type_name == 'dict' and type(schema) is dict:
            return Utils.sanitize_dict(d, schema, is_delete_extra)
        elif type_name == 'list' and type(schema) is list:
            for i in range(0, len(d)):
                if Utils.sanitize_type(d[i], schema[0], is_delete_extra) == False:
                    return False
        else:
            types = schema.split(',')
            
            for i in range(0, len(types)):
                if type_name == types[i]:
                    return True
                
            return False

        return True

    @staticmethod
    def sanitize_dict(d, schema, is_delete_extra = True):
        ret = 1

        if is_delete_extra == True:  
            keys = d.keys()

            for i in range(0, len(keys)):
                if schema.has_key(keys[i]) == False:
                    del d[keys[i]]
                    continue

        depends_check_keys = []

        for key in schema:
            is_optional = schema[key].get('optional', False)

            if d.has_key(key) == False:
                ret = 0 if is_optional == False else ret
            else:
                if schema[key].has_key('depends') == True:
                    depends_check_keys.append(key)

                if Utils.sanitize_type(d[key], schema[key]['type'], is_delete_extra) == False:
                    del d[key]
                    ret = 0 if is_optional == False else ret                

        for j in range(0, len(depends_check_keys)):
            depends = schema[depends_check_keys[j]]['depends']

            for i in range(0, len(depends)):
                if d.has_key(depends[i]) == False:
                    if d.has_key(depends_check_keys[j]):
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
        
    def __getattr__(self, attr):
        return self.data.get(attr)
        
    @staticmethod
    def parse(file, is_data = False):
        value = {}

        if is_data == True or os.path.isfile(file) == True:        
            try:
                data = file

                if is_data != True:
                    f = open(file, 'r')
                    data = f.read()
                    f.close()
                    data = re.sub('#.*\n', '', data)
                    value = json.loads(data)
                elif type(data) == 'dict':
                    value = dict
                else:
                    data = re.sub('#.*\n', '', data)
                    value = json.loads(data)
            except:
                pass

        return value
        
    def save(self):
        if self.file != None:
            f = open(self.file, 'w')
            json.dump(data, f)
            data = f.read()
            f.close()
            
    def set(self, data = None):
        is_data = True
        
        if data == None:
            if self.file == None:
                return
            
            data = self.file
            is_data = False
            
        config = Config.parse(data, is_data)
        
        if Utils.sanitize_dict(config, self.schema) == False:
            if is_data == False:
                raise RuntimeError, self.file + ' is either missing or currupted' 
            else:
                raise RuntimeError, 'Invalid config' 

        self.data = config
        
    def update(self, data):
        config = {}
        config.update(self.data)
        config.update(Config.parse(data, True))
        self.set(config)
        
class SealionConfig(Config):
    def __init__(self, file):
        Config.__init__(self)
        self.file = file
        self.schema = {
            'proxy': {'type': {'https_proxy': {'type': 'str,unicode', 'optional': True}}, 'optional': True},
            'whitelist': {'type': ['str,unicode'], 'optional': True},
            'variables': {
                'type': [{'name': {'type': 'str,unicode'}, 'value': {'type': 'str,unicode'}}],
                'optional': True
            }    
        }
        
class AgentConfig(Config):
    def __init__(self, file):
        Config.__init__(self)
        self.file = file
        self.schema = {
            'token': {'type': 'str,unicode'},
            'id': {'type': 'str,unicode', 'depends': ['version'], 'optional': True},
            'host': {'type': 'str,unicode'},
            'version': {'type': 'str,unicode', 'depends': ['id'], 'optional': True},
            'activities': {
                'type': [{'_id': {'type': 'str,unicode'}, 'name': {'type': 'str,unicode'}, 'command': {'type': 'str,unicode'}}],
                'depends': ['id', 'version'],
                'optional': True
            }    
        }
    
    def set(self, data = None):
        Config.set(self, data)
        self.data['host'] = self.data['host'].strip()
        length = len(self.data['host'])

        if length and self.data['host'][length - 1] == '/':
            self.data['host'] = self.data['host'][:-1]
    
class Globals:
    __metaclass__ = SingletonType
    
    def __init__(self):
        exe_path = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
        self.exe_path = exe_path if (exe_path[len(exe_path) - 1] == '/') else (exe_path + '/')
        self.lock_file = Utils.get_safe_path(self.exe_path + 'var/run/sealion.pid')
        self.agent_config_file = Utils.get_safe_path(self.exe_path + 'etc/config/agent_config.json')
        self.sealion_config_file = Utils.get_safe_path(self.exe_path + 'etc/config/sealion_config.json')
        self.config = EmptyClass()
        self.config.sealion = SealionConfig(self.sealion_config_file)
        self.config.agent = AgentConfig(self.agent_config_file)
        self.config.sealion.set()
        self.config.agent.set()

        if hasattr(self.config.agent, 'id') == False:
            print 'no id'
    
    def url(self, path = ''):
        path.strip()
        
        if len(path):
            path = path if path[0] == '/' else ('/' + path)
                  
        return self.config.agent.host + path

try:
    Globals()
except RuntimeError, e:
    print e
    exit()

