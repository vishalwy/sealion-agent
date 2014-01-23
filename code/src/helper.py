import threading
import pdb
import os
import sys
import json
import re
import api
import rtc
from constructs import *
   
class Utils(Namespace):
    @staticmethod
    def sanitize_type(d, schema, is_delete_extra = True, regex = None):
        type_name = type(d).__name__

        if type_name == 'dict' and type(schema) is dict:
            return Utils.sanitize_dict(d, schema, is_delete_extra)
        elif type_name == 'list' and type(schema) is list:
            for i in range(0, len(d)):
                if Utils.sanitize_type(d[i], schema[0], is_delete_extra, regex) == False:
                    return False
                
            return True
        else:
            types = schema.split(',')
            flag = False
            
            for i in range(0, len(types)):
                if type_name == types[i]:
                    flag = True
                    break
                    
            if flag == True and (type_name == 'str' or type_name == 'unicode') and regex != None:
                if re.compile(regex).match(d) == None:
                    return False
                
            return flag

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

                if Utils.sanitize_type(d[key], schema[key]['type'], is_delete_extra, schema[key].get('regex')) == False:
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
        return self.data[attr]
        
    def get_dict(self, keys = None, as_dict = True):
        return DictEx(self.data).get_dict(keys, as_dict)
        
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
                elif type(data) is dict:
                    value = data
                else:
                    data = re.sub('#.*\n', '', data)
                    value = json.loads(data)
            except:
                pass

        return value
        
    def save(self):
        if self.file != None:
            f = open(self.file, 'w')
            json.dump(self.data, f)
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
            'orgToken': {'type': 'str,unicode', 'depends': ['name'], 'regex': '^[a-zA-Z0-9\-]{36}$'},
            '_id': {'type': 'str,unicode', 'depends': ['agentVersion'], 'regex': '^[a-zA-Z0-9]{24}$', 'optional': True},
            'apiUrl': {'type': 'str,unicode', 'regex': '^https://[^\s:]+(:[0-9]+)?$' },
            'name': {'type': 'str,unicode',  'regex': '^.+$'},
            'category': {'type': 'str,unicode', 'regex': '^.+$', 'optional': True},
            'agentVersion': {'type': 'str,unicode', 'depends': ['_id'], 'regex': '^[0-9\.]+$', 'optional': True},
            'activities': {
                'type': [{
                    '_id': {'type': 'str,unicode', 'regex': '^[a-zA-Z0-9]{24}$'}, 
                    'name': {'type': 'str,unicode', 'regex': '^.+$'}, 
                    'command': {'type': 'str,unicode', 'regex': '^.+$'}
                }],
                'depends': ['_id', 'agentVersion'],
                'optional': True
            }    
        }
        
class ConnectThread(threading.Thread):
    def run(self):
        globals = Globals()
        globals.api.authenticate() and globals.rtc.connect().start()
        
    def connect(self):
        globals = Globals()
        
        if hasattr(globals.config.agent, 'activities') == False:
            self.run()
        else:   
            self.start()
    
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
        self.api = api.Interface(self.config)
        self.rtc = rtc.Interface(self.api)

        if hasattr(self.config.agent, '_id') == False and self.api.register() == False:
            exit()            
    
    def url(self, path = ''):
        return self.api.get_url(path);
    
    def connect(self):
        ConnectThread().connect()

try:
    Globals()
except RuntimeError, e:
    print e
    exit()
