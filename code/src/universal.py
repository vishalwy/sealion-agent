"""
Abstracts configuration and universal for SeaLion agent.
Implements SealionConfig, AgentConfig and Universal
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import threading
import os
import pwd
import logging
import platform
import sys
import time
import multiprocessing
import re
import requests
import helper
import version
from datetime import datetime
from constructs import *

_log = logging.getLogger(__name__)  #module level logging

class SealionConfig(helper.Config):
    """
    Implements configurable settings for the agent.
    """
    
    #schema defining possible keys and values for this class. check helper.Config for details
    schema = {
        'whitelist': {
            'type': ['str,unicode'], 
            'regex': True,
            'optional': True
        },
        'env': {
            'type': {
                re.compile('^.+$'): {
                    'type': 'str,unicode'
                }
            },
            'optional': True
        },
        'logging': {
            'type': {
                'level': {
                    'type': 'str,unicode', 
                    'regex': '^\s*(info|error|debug|none)\s*$', 
                    'optional': True
                },
                'modules': {
                    'type': ['str,unicode'], 
                    'depends': ['level'], 
                    'regex': True, 
                    'optional': True, 
                }
            },
            'optional': True
        },
        'commandTimeout': {
            'type': 'int,float', 
            'optional': True, 
            'regex': '^\+?((0?[5-9]{1}|(0?[1-9][0-9]+))|((0?[5-9]{1}|(0?[1-9][0-9]+))\.[0-9]*))$'
        },
        'user': {
            'type': 'str,unicode', 
            'regex': '^.+$', 
            'optional': True
        },
        'builtinParser': {
            'type': 'bool',
            'optional': True
        }
    }
   
class AgentConfig(helper.Config):
    """
    Implements private settings for the agent.
    """
    
    #schema defining possible keys and values for this class. check helper.Config for details
    schema = {
        'orgToken': {
            'type': 'str,unicode', 
            'regex': '^[a-zA-Z0-9\-]{36}$'
        },
        
        'apiUrl': {
            'type': 'str,unicode', 
            'regex': '^https://[^\s:]+(:[0-9]+)?$' 
        },
        
        'category': {
            'type': 'str,unicode', 
            'regex': '^.+$', 
            'optional': True
        },
        
        'ref': {
            'type': 'str,unicode', 
            'regex': 'curl|tarball', 
            'optional': True
        },
        
        'config': {
            'type': {
                '_id': {
                    'type': 'str,unicode', 
                    'regex': '^[a-zA-Z0-9]{24}$', 
                    'optional': True
                },
                
                'name': {
                    'type': 'str,unicode', 
                    'regex': '^.+$',
                    'optional': True
                },
                
                'activities': {
                    'type': [{
                        '_id': {
                            'type': 'str,unicode', 
                            'regex': '^[a-zA-Z0-9]{24}$'
                        }, 
                        'name': {
                            'type': 'str,unicode', 
                            'regex': '^.+$'
                        },
                        'service': {
                            'type': 'str,unicode', 
                            'regex': '^.+$', 
                            'optional': True
                        },
                        'command': {
                            'type': 'str,unicode', 
                            'regex': '^.+$'
                        },
                        'interval': {'type': 'int'}
                    }],
                    'depends': ['_id'],
                    'optional': True
                },
                
                'org': {
                    'type': 'str,unicode', 
                    'depends': ['_id'], 
                    'regex': '^[a-zA-Z0-9]{24}$', 
                    'optional': True
                },
                
                'envVariables': {
                    'type': {
                        re.compile('^[a-zA-Z_][a-zA-Z0-9_]*$'): {
                            'type': 'str,unicode'
                        }
                    }, 
                    'depends': ['_id'],
                    'optional': True
                }
            },
            
            'depends': ['orgToken']
        }
    }
    
    def update(self, data):   
        """
        Public method to update the config.
        
        Args:
            data: dict containing modified config
            
        Returns:
            True on success, an error string on failure
        """
            
        univ, version = Universal(), None
        
        if data.get('config'):
            version = data.get('config').get('agentVersion')
             
        if version and version != self.private_data['agentVersion']:  #if the agent version mismatch we need to update the agent
            self.get(['config', '_id']) and univ.event_dispatcher.trigger('update_agent')  #trigger an event so that the other module can install the update
            
        ret = helper.Config.update(self, data)  #call the base class version
        univ.event_dispatcher.trigger('set_exec_details')  #trigger an event so that the other modules can act on the new activities/env
        return ret

class Universal(singleton()):
    """
    Implements global variables as a singleton class
    """
    
    def __init__(self):
        """
        Constructor
        """
        
        cur_time = time.time()
        self.metric = {'starting_time': cur_time, 'stopping_time': cur_time}  #save the timestamps
        self.exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]  #absolute path of the base dir, as it is one level up
        self.is_update_only_mode = False  #no update only mode
        self.main_script = helper.main_script  #main script
        self.event_dispatcher = helper.event_dispatcher  #event dispatcher for communication across modules
        self.config = EmptyClass()
        self.config.sealion = SealionConfig(self.exe_path + '/etc/config.json')  #instance of configurable settings
        self.config.agent = AgentConfig(file = self.exe_path + '/etc/agent.json', private_data = {'agentVersion': version.__version__})  #instance of private settings
        ret = self.config.sealion.set()  #load the config from the file
        
        if ret != True:  #raise an exception on error
            raise RuntimeError(ret)
        
        os.environ.update(self.config.sealion.get_dict(('env', {}))['env'])  #export the env vars defined in the config
        ret = self.config.agent.set()  #load private config from the file
        
        if ret != True:  #raise an exception on error
            raise RuntimeError(ret)
        
        self.db_path = helper.Utils.get_safe_path(self.exe_path + '/var/db/')  #absolute path to database dir
        self.temp_path = helper.Utils.get_safe_path(self.exe_path + '/tmp/')  #absolute path to temporary dir
        self.stop_event = threading.Event()  #event that tells whether the agent should stop
        self.post_event = threading.Event()  #event that tell whether the api.session can request
        self.proxy_url = requests.utils.get_environ_proxies(self.config.agent.apiUrl).get('https', '')  #proxy url for api
        uname = platform.uname()  #platform uname
        dist = platform.linux_distribution()  #platform distribution
        dist = dist if dist[0] else platform.linux_distribution(supported_dists = ['system'])
        dist = dist if dist[0] else ('Unknown', 'Unknown', 'Unknown')
        
        #various system details
        self.details = {
            'user': pwd.getpwuid(os.getuid())[0],
            'type': uname[0],
            'kernel': uname[2],
            'arch': platform.machine(),
            'pythonVersion': '%s %s' % (platform.python_implementation(), '.'.join([unicode(i) for i in sys.version_info])),
            'cpuCount': multiprocessing.cpu_count(),
            'isProxy': True if self.proxy_url else False,
            'dist': {
                'name': dist[0],
                'version': dist[1],
                'codeName': dist[2]
            }
        }
        
    def get_run_time(self):
        """
        Public method to get the total run time.
        
        Returns:
            Run time in seconds
        """
        
        return time.time() - self.metric['starting_time']
    
    def set_time_metric(self, metric):
        """
        Public method to set the time metric.
        
        Args:
            metric: the metric to set
        """
        
        self.metric[metric] = time.time()
        
    def get_time_metric(self, metric):
        """
        Public method to get the time metric.
        
        Args:
            metric: the metric to get
            
        Returns:
            The value for the metric given.
        """
        
        return self.metric[metric]
        
    def get_stoppage_time(self):
        """
        Public method to get time taken to stop the agent.
        
        Returns:
            Time taken in seconds
        """
        
        return time.time() - self.metric['stopping_time']
    
    def get_run_time_str(self):
        """
        Public method to get the total run time as a readable string.
        
        Returns:
            A string representing the total run time.
        """
        
        return unicode(datetime.now() - datetime.fromtimestamp(self.metric['starting_time']))
    
    def get_url(self, path = ''):
        """
        Public method to get the complete url for the given path.
        
        Args:
            path: the url to be concatenated
            
        Returns:
            The complete url
        """
        
        path.strip()
        
        if len(path):
            path = path if path[0] == '/' else ('/' + path)
                  
        return self.config.agent.apiUrl + path
