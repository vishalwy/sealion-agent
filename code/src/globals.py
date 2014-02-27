import threading
import os
import gc
import logging
import api
import rtc
import storage
from helper import Utils, Config
from constructs import *

_log = logging.getLogger(__name__)

class SealionConfig(Config):
    def __init__(self, file):
        Config.__init__(self)
        self.file = file
        self.schema = {
            'whitelist': {'type': ['str,unicode'], 'optional': True, 'is_regex': True},
            'env': {
                'type': [{'.': {'type': 'str,unicode'}}],
                'optional': True
            },
            'logging': {
                'type': {
                    'level': {'type': 'str,unicode', 'regex': '^\s*(info|error|debug|none)\s*$', 'optional': True},
                    'modules': {'type': ['str,unicode'], 'depends': ['level'], 'regex': '^.+$', 'optional': True}
                },
                'optional': True
            },
            'commandTimeout': {'type': 'int,float', 'optional': True, 'regex': '^\+?((0?[5-9]{1}|(0?[1-9][0-9]+))|((0?[5-9]{1}|(0?[1-9][0-9]+))\.[0-9]*))$'}
        }
        
    def set(self, data = None):
        ret = Config.set(self, data)
        variables = self.data['env'] if ('env' in self.data) else []
        
        for i in range(0, len(variables)):
            for key in variables[i]:
                os.environ[key] = variables[i][key]
            
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
            'agentVersion': {'type': 'str,unicode', 'regex': '^[0-9\.]+$'},
            'activities': {
                'type': [{
                    '_id': {'type': 'str,unicode', 'regex': '^[a-zA-Z0-9]{24}$'}, 
                    'name': {'type': 'str,unicode', 'regex': '^.+$'}, 
                    'command': {'type': 'str,unicode', 'regex': '^.+$'},
                    'interval': {'type': 'int'}
                }],
                'depends': ['_id', 'agentVersion'],
                'optional': True
            },
            'updateUrl': {'type': 'str,unicode', 'regex': '^.+$'},
            'org': {'type': 'str,unicode', 'depends': ['orgToken', '_id', 'agentVersion'], 'regex': '^[a-zA-Z0-9]{24}$', 'optional': True}
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
        if ('category' in data):
            del data['category']
            
        globals = Globals()
        version = data.get('agentVersion')
             
        if version and version != self.data['agentVersion']:
            del data['agentVersion']
            globals.api.update_agent()
            
        self.lock.acquire()
        old_activities = self.data['activities'] if ('activities' in self.data) else []
        ret = Config.update(self, data)
        new_activities = self.data['activities'] if ('activities' in self.data) else []
        self.lock.release()
        
        if globals.activities == None:
            return ret
        
        deleted_activity_ids = self.get_deleted_activities(old_activities, new_activities)
        globals.manage_activities(old_activities, deleted_activity_ids)
        return ret

class Interface(SingletonType('GlobalsMetaClass', (object, ), {})):
    def __init__(self):
        exe_path = os.path.dirname(os.path.abspath(__file__))
        exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
        self.exe_path = exe_path[:exe_path.rfind('/') + 1]
        self.db_path = Utils.get_safe_path(self.exe_path + 'var/db/')
        self.is_update_only_mode = False
        self.config = EmptyClass()
        self.config.sealion = SealionConfig(Utils.get_safe_path(self.exe_path + 'etc/config.json'))
        self.config.agent = AgentConfig(Utils.get_safe_path(self.exe_path + 'etc/agent.json'))
        self.APIStatus = api.Status
        ret = self.config.sealion.set()
        
        if ret != True:
            raise RuntimeError(ret)
        
        ret = self.config.agent.set()
        
        if ret != True:
            raise RuntimeError(ret)
        
        self.activities = None
        self.stop_event = threading.Event()
        self.api = api.Interface(self.config, self.stop_event)
        self.reset_rtc_interface()
        self.store = storage.Interface(self.api, self.db_path)
        
    def url(self, path = ''):
        return self.api.get_url(path);
    
    def reset_rtc_interface(self):
        self.rtc = None
        _log.debug('GC collected %d unreachables' % gc.collect())
        self.rtc = rtc.Interface(self.api)
        
    def manage_activities(self, old_activities = [], deleted_activity_ids = []):
        self.activities = self.activities or {}
        new_activities = self.config.agent.activities
        start_count, update_count, stop_count = 0, 0, 0
        
        for activity_id in deleted_activity_ids:
            self.activities[activity_id].stop()
            del self.activities[activity_id]
            stop_count += 1
            
        stop_count and self.store.clear_activities(deleted_activity_ids)
        self.store.set_valid_activities([activity['_id'] for activity in new_activities])
            
        for activity in new_activities:
            activity_id = activity['_id']
            
            if (activity_id in self.activities):
                t = [old_activity for old_activity in old_activities if old_activity['_id'] == activity_id]
                
                if len(t) and t[0]['interval'] == activity['interval'] and t[0]['command'] == activity['command']:
                    continue
                
                self.activities[activity_id].stop()
                update_count += 1
            else:
                start_count += 1
                
            self.activities[activity_id] = self.activity_type(activity)
            self.activities[activity_id].start()
            
        _log.info('%d started; %d updated; %d stopped' % (start_count, update_count, stop_count))

Globals = Interface