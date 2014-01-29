import threading
import os
import api
import rtc
import storage
from helper import *

class SealionConfig(Config):
    def __init__(self, file):
        Config.__init__(self)
        self.file = file
        self.schema = {
            'proxy': {
                'type': {
                    'https': {'type': 'str,unicode', 'optional': True}, 
                    'http': {'type': 'str,unicode', 'optional': True}
                },
                'optional': True
            },
            'whitelist': {'type': ['str,unicode'], 'optional': True, 'is_regex': True},
            'env': {
                'type': [{'name': {'type': 'str,unicode'}, 'value': {'type': 'str,unicode'}}],
                'optional': True
            },
            'logging': {
                'type': {
                    'level': {'type': 'str,unicode', 'regex': '^\s*(info|error|debug|none)\s*$', 'optional': True},
                    'modules': {'type': ['str,unicode'], 'depends': ['level'], 'regex': '^.+$', 'optional': True}
                },
                'optional': True
            }
        }
        
    def set(self, data = None):
        ret = Config.set(self, data)
        variables = self.data['env'] if self.data.has_key('env') else []
        
        for i in range(0, len(variables)):
            os.environ[variables[i]['name']] = variables[i]['value']
            
        return ret        
        
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
                    'command': {'type': 'str,unicode', 'regex': '^.+$'},
                    'interval': {'type': 'int'}
                }],
                'depends': ['_id', 'agentVersion'],
                'optional': True
            }    
        }
        
    def get_deleted_activities(self, old_activities, new_activities):
        deleted_activities = []
        
        for old_activity in old_activities:
            activity = old_activity['_id']
            
            for new_activity in new_activities:
                if new_activity['_id'] == activity:
                    activity = None
                    break
                    
            if activity != None:
                deleted_activities.append(activity)
                
        return deleted_activities
        
    def update(self, data):       
        if data.has_key('category'):
            del data['category']
            
        self.lock.acquire()
        old_activities = self.data['activities'] if self.data.has_key('activities') else []
        ret = Config.update(self, data)
        new_activities = self.data['activities'] if self.data.has_key('activities') else []
        self.lock.release()
        globals = Globals()
        
        if globals.activities == None:
            return ret
        
        deleted_activity_ids = self.get_deleted_activities(old_activities, new_activities)
        globals.manage_activities(old_activities, deleted_activity_ids)
        return ret

class Globals:
    __metaclass__ = SingletonType
    
    def __init__(self):
        self.exe_path = Utils.get_exe_path()
        self.lock_file = Utils.get_safe_path(self.exe_path + 'var/run/sealion.pid')
        self.config = EmptyClass()
        self.config.sealion = SealionConfig(Utils.get_safe_path(self.exe_path + 'etc/config/sealion.json'))
        self.config.agent = AgentConfig(Utils.get_safe_path(self.exe_path + 'etc/config/agent.json'))
        self.APIStatus = api.Status
        ret = self.config.sealion.set()
        
        if ret != True:
            raise RuntimeError, ret
        
        ret = self.config.agent.set()
        
        if ret != True:
            raise RuntimeError, ret
        
        self.reset()
        
    def url(self, path = ''):
        return self.api.get_url(path);
    
    def reset(self):
        self.stop_event = threading.Event()
        self.api = api.Interface(self.config, self.stop_event)
        self.rtc = rtc.Interface(self.api)   
        self.store = storage.Interface(Utils.get_safe_path(self.exe_path + 'var/dbs/' + self.config.agent.orgToken + '.db'), self.api)
        self.activities = None
        
    def manage_activities(self, old_activities = [], deleted_activity_ids = []):
        self.activities = self.activities or {}
        new_activities = self.config.agent.activities
        
        for activity_id in deleted_activity_ids:
            self.activities[activity_id].stop()
            del self.activities[activity_id]
            
        for activity in new_activities:
            activity_id = activity['_id']
            
            if self.activities.has_key(activity_id):
                t = [old_activity for old_activity in old_activities if old_activity['_id'] == activity_id]
                
                if len(t) and t[0]['interval'] == activity['interval'] and t[0]['command'] == activity['command']:
                    continue
                
                self.activities[activity_id].stop()
                
            self.activities[activity_id] = self.activity_type(activity, self.stop_event)
            self.activities[activity_id].start()


