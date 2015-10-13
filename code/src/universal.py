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
import requests
import helper
from datetime import datetime
from constructs import *

_log = logging.getLogger(__name__)  #module level logging

class SealionConfig(helper.Config):
    """
    Implements configurable settings for the agent.
    """
    
    #schema defining possible keys and values for this class. check helper.Config for details
    schema = {
        'whitelist': {'type': ['str,unicode'], 'optional': True, 'is_regex': True},
        'env': {
            'type': [{'.': {'type': 'str,unicode'}}],
            'optional': True
        },
        'logging': {
            'type': {
                'level': {'type': 'str,unicode', 'regex': '^\s*(info|error|debug|none)\s*$', 'optional': True},
                'modules': {'type': ['str,unicode'], 'depends': ['level'], 'regex': '^.+$', 'optional': True, 'is_regex': True}
            },
            'optional': True
        },
        'commandTimeout': {
            'type': 'int,float', 
            'optional': True, 
            'regex': '^\+?((0?[5-9]{1}|(0?[1-9][0-9]+))|((0?[5-9]{1}|(0?[1-9][0-9]+))\.[0-9]*))$'
        },
        'user': {'type': 'str,unicode', 'regex': '^.+$', 'optional': True}
    }
    
    def __init__(self, file):
        """
        Constructor.
        
        Args:
            file: file containing the settings in JSON format
        """
        
        helper.Config.__init__(self)  #initialize base class
        self.file = file  #settings file
        
    def set(self, data = None):
        """
        Public method to set the config.
        
        Args:
            data: dict containing new config
            
        Returns:
            True on success, an error string on failure
        """
        
        ret = helper.Config.set(self, data)  #call the base class version
        variables = self.data.get('env', [])  #get environment variable defined
        
        #loop through the variables and export in the current environment
        #this will help one to hide passwords and such information from the command
        for i in range(0, len(variables)): 
            for key in variables[i]:
                os.environ[key] = variables[i][key]
            
        return ret        
        
class AgentConfig(helper.Config):
    """
    Implements private settings for the agent.
    """
    
    #schema defining possible keys and values for this class. check helper.Config for details
    schema = {
        'orgToken': {'type': 'str,unicode', 'depends': ['name'], 'regex': '^[a-zA-Z0-9\-]{36}$'},
        '_id': {'type': 'str,unicode', 'depends': ['agentVersion'], 'regex': '^[a-zA-Z0-9]{24}$', 'optional': True},
        'apiUrl': {'type': 'str,unicode', 'regex': '^https://[^\s:]+(:[0-9]+)?$' },
        'name': {'type': 'str,unicode',  'regex': '^.+$'},
        'category': {'type': 'str,unicode', 'regex': '^.+$', 'optional': True},
        'agentVersion': {'type': 'str,unicode', 'regex': '^(\d+\.){2}\d+(\.[a-z0-9]+)?$'},
        'activities': {
            'type': [{
                '_id': {'type': 'str,unicode', 'regex': '^[a-zA-Z0-9]{24}$'}, 
                'name': {'type': 'str,unicode', 'regex': '^.+$'},
                'service': {'type': 'str,unicode', 'regex': '^.+$', 'optional': True},
                'command': {'type': 'str,unicode', 'regex': '^.+$'},
                'interval': {'type': 'int'}
            }],
            'depends': ['_id', 'agentVersion'],
            'optional': True
        },
        'org': {'type': 'str,unicode', 'depends': ['orgToken', '_id', 'agentVersion'], 'regex': '^[a-zA-Z0-9]{24}$', 'optional': True},
        'ref': {'type': 'str,unicode', 'depends': ['orgToken', 'agentVersion'], 'regex': 'curl|tarball', 'optional': True},
        'updateUrl': {'type': 'str,unicode', 'optional': True},
        'envVariables': {'type': {'.': {'type': 'str,unicode'}}, 'optional': True}
    }
    
    def __init__(self, file):
        """
        Constructor.
        
        Args:
            file: file containing the settings in JSON format
        """
        
        helper.Config.__init__(self)  #initialize base class
        self.file = file  #settings file
        
    def update(self, data):   
        """
        Public method to update the config.
        
        Args:
            data: dict containing new config
            
        Returns:
            True on success, an error string on failure
        """
        
        if 'category' in data:  #delete the category key from data since category in the settings file is the name, and data['category'] is the id
            del data['category']
            
        univ = Universal()
        version = data.get('agentVersion')
             
        if version and version != self.data['agentVersion']:  #if the agent version mismatch we need to update the agent
            hasattr(self, '_id') and univ.event_dispatcher.trigger('update_agent')  #trigger an event so that the other module can install the update
            del data['agentVersion']  #delete the key as we want only the updater script to modify it
            
        ret = helper.Config.update(self, data)  #call the base class version
        univ.event_dispatcher.trigger('set_activities')  #trigger an event so that the other modules can act on the new activities
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
        self.main_script = helper.main_script  #main script
        self.is_update_only_mode = False  #no update only mode
        self.config = EmptyClass()
        self.config.sealion = SealionConfig(self.exe_path + '/etc/config.json')  #instance of configurable settings
        self.config.agent = AgentConfig(self.exe_path + '/etc/agent.json')  #instance of private settings
        ret = self.config.sealion.set()  #load the config from the file
        
        if ret != True:  #raise an exception on error
            raise RuntimeError(ret)
        
        ret = self.config.agent.set()  #load private config from the file
        
        if ret != True:  #raise an exception on error
            raise RuntimeError(ret)
        
        self.db_path = helper.Utils.get_safe_path(self.exe_path + '/var/db/')  #absolute path to database dir
        self.temp_path = helper.Utils.get_safe_path(self.exe_path + '/tmp/')  #absolute path to temporary dir
        self.stop_event = threading.Event()  #event that tells whether the agent should stop
        self.post_event = threading.Event()  #event that tell whether the api.session can request
        self.event_dispatcher = helper.event_dispatcher  #event dispatcher for communication across modules
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
        
