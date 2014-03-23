__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import threading
import os
import logging
import helper
import exit_status
from constructs import *

_log = logging.getLogger(__name__)

class SealionConfig(helper.Config):
    def __init__(self, file):
        helper.Config.__init__(self)
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
        ret = helper.Config.set(self, data)
        variables = self.data['env'] if ('env' in self.data) else []
        
        for i in range(0, len(variables)):
            for key in variables[i]:
                os.environ[key] = variables[i][key]
            
        return ret        
        
class AgentConfig(helper.Config):
    def __init__(self, file):
        helper.Config.__init__(self)
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
            'org': {'type': 'str,unicode', 'depends': ['orgToken', '_id', 'agentVersion'], 'regex': '^[a-zA-Z0-9]{24}$', 'optional': True},
            'ref': {'type': 'str,unicode', 'depends': ['orgToken', 'agentVersion'], 'regex': 'curl|tarball', 'optional': True}
        }
        
    def update(self, data):   
        if ('category' in data):
            del data['category']
            
        globals = Globals()
        version = data.get('agentVersion')
             
        if version and version != self.data['agentVersion']:
            del data['agentVersion']
            hasattr(self, '_id') and globals.event_dispatcher.trigger('update_agent')
            
        ret = helper.Config.update(self, data)
        globals.event_dispatcher.trigger('set_activities')
        return ret

class Globals(SingletonType('GlobalsMetaClass', (object, ), {})):
    def __init__(self):
        self.stop_status = exit_status.AGENT_ERR_SUCCESS
        exe_path = os.path.dirname(os.path.abspath(__file__))
        exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
        self.exe_path = exe_path[:exe_path.rfind('/') + 1]
        self.db_path = helper.Utils.get_safe_path(self.exe_path + 'var/db/')
        self.is_update_only_mode = False
        self.config = EmptyClass()
        self.config.sealion = SealionConfig(helper.Utils.get_safe_path(self.exe_path + 'etc/config.json'))
        self.config.agent = AgentConfig(helper.Utils.get_safe_path(self.exe_path + 'etc/agent.json'))
        ret = self.config.sealion.set()
        
        if ret != True:
            raise RuntimeError(ret)
        
        ret = self.config.agent.set()
        
        if ret != True:
            raise RuntimeError(ret)
        
        self.activities = None
        self.stop_event = threading.Event()
        self.post_event = threading.Event()
        self.event_dispatcher = EventDispatcher()
