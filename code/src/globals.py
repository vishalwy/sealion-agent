import pdb
import time
import threading
import sys
import api
import rtc
from helper import *

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
        self.attempt(-1)
    
    def attempt(self, max_try = 5):
        globals = Globals()
        res = globals.api.authenticate(max_try)
        res == True and globals.rtc.connect().start()
        return res            
        
    def connect(self):
        globals = Globals()
        
        if hasattr(globals.config.agent, '_id') == False and globals.api.register() != True:
            return False
        
        res = self.attempt()
        
        if res == None:
            res = hasattr(globals.config.agent, 'activities')
            res and self.start()            
            
        return res
    
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
        ret = self.config.sealion.set()
        
        if ret != True:
            raise RuntimeError, ret
        
        ret = self.config.agent.set()
        
        if ret != True:
            raise RuntimeError, ret
        
        self.api = api.Interface(self.config)
        self.rtc = rtc.Interface(self.api)            
    
    def url(self, path = ''):
        return self.api.get_url(path);
    
    def connect(self):
        ConnectThread().connect()

    


