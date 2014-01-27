import threading
import api
import rtc
from helper import *
from storage import OfflineStore

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
            },
            'logging': {
                'type': {
                    'level': {'type': 'str,unicode', 'regex': '^\s*(info|error|debug|none)\s*$', 'optional': True},
                    'modules': {'type': ['str,unicode'], 'depends': ['level'], 'regex': '^.+$', 'optional': True}
                },
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
                    'command': {'type': 'str,unicode', 'regex': '^.+$'},
                    'interval': {'type': 'int'}
                }],
                'depends': ['_id', 'agentVersion'],
                'optional': True
            }    
        }
        
    def get_changes(self, old_activities, new_activities):
        old_set = set(tuple([tuple(activity.items()) for activity in old_activities]))
        new_set = set(tuple([tuple(activity.items()) for activity in new_activities]))
        
        inserted = [dict(elem) for elem in new_set - old_set]
        deleted = [dict(elem) for elem in old_set - new_set]
        updated = []
        i = len(inserted) - 1
        
        while i >= 0:
            if next((item for item in deleted if item['_id'] == inserted[i]['_id']), None):
                updated.append(inserted[i])
                deleted.remove(inserted[i])
                inserted.pop(i)
                
            i -= 1
                
        return {'inserted': inserted, 'updated': updated, 'deleted': deleted}
        
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
        
        changes = self.get_changes(old_activities, new_activities)
        
        for activity in changes['deleted']:
            globals.activities[activity['_id']].stop()
            del globals.activities[activity['_id']]
            
        for activity in changes['updated']:
            globals.activities[activity['_id']].stop()
            globals.activities[activity['_id']] = globals.activity_type(activity, globals.stop_event)
            
        for activity in changes['inserted']:
            globals.activities[activity['_id']] = globals.activity_type(activity, globals.stop_event)
            globals.activities[activity['_id']].start()
        
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
        self.off_store = OfflineStore(Utils.get_safe_path(self.exe_path + 'var/dbs/' + self.config.agent.orgToken + '.db'), self.api)
        self.activities = None

