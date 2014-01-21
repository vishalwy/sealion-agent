import os
import sys
import json
import re

def is_success(response):
    return True if (response.status_code == 304 or (response.status_code >= 200 and response.status_code < 300)) else False

def get_complete_url(url, is_socket_io = False):
    base_url = globals['agent_config'] + ('' if is_socket_io else '/agents')
    base_url = base_url if url[0] == '/' else (base_url + '/')
    base_url = base_url + ('' if is_socket_io else url)
    return base_url

def sanitize_type(d, schema, is_delete_extra = True):
    type_name = type(d).__name__

    if type_name == 'dict' and type(schema) is dict:
        return sanitize_dict(d, schema, is_delete_extra)
    elif type_name == 'list' and type(schema) is list:
        for i in range(0, len(d)):
            if sanitize_type(d[i], schema[0], is_delete_extra) == False:
                return False
    elif type_name != schema:
        return False
        
    return True

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
                    
            if sanitize_type(d[key], schema[key]['type'], is_delete_extra) == False:
                del d[key]
                ret = 0 if is_optional == False else ret                
    
    for j in range(0, len(depends_check_keys)):
        depends = schema[depends_check_keys[j]]['depends']
               
        for i in range(0, len(depends)):
            if d.has_key(depends[i]) == False:
                del d[depends_check_keys[j]]
                break
                
    return False if ret == 0 else True

def get_safe_path(path):
    dir = os.path.dirname(path)
    
    if os.path.isdir(path) != True:
        os.makedirs(dir)
        
    return path

def get_config(file, is_data = False):
    value = {}
    
    if is_data == True or os.path.isfile(file) == True:        
        try:
            data = file
            
            if is_data != True:
                f = open(file, 'r')
                data = f.read()
                f.close()
                
            if type(data) == 'dict':
                value = dict
            else:
                data = re.sub('#.*\n', '', data)
                value = json.load(data)
        except:
            pass
    
    return value

def get_agent_config(file, is_data = False):
    config = get_config(file, is_data)
    schema = {
        'token': {'type': 'str'},
        'id': {'type': 'str', 'depends': ['version'], 'optional': True},
        'host': {'type': 'str'},
        'version': {'type': 'str', 'depends': ['id'], 'optional': True},
        'activities': {
            'type': [{'_id': {'type': 'str'}, 'name': {'type': 'str'}, 'command': {'type': 'str'}}],
            'depends': ['id', 'version'],
            'optional': True
        }    
    }
    
    if sanitize_dict(config, schema) == False:
        return None
        
    return config

def get_sealion_config(file, is_data = False):
    config = get_config(file, is_data)
    schema = {
        'proxy': {'type': {'https_proxy': {'type': 'str', 'optional': True}}},
        'whitelist': {'type': ['str'], 'optional': True},
        'variables': {
            'type': [{'name': {'type': 'str'}, 'value': {'type': 'str'}}],
            'optional': True
        }    
    }
    
    if sanitize_dict(config, schema) == False:
        return None
        
    return config

def init_globals():
    global globals
    
    if globals != None:
        return
    
    exe_path = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
    globals['exe_path'] = exe_path if (exe_path[len(exe_path) - 1] == '/') else (exe_path + '/')
    globals['lock_file'] = get_safe_path(globals['exe_path'] + 'var/run/sealion.pid')
    globals['agent_config_file'] = get_safe_path(globals['exe_path'] + 'etc/config/agent_config.json')
    globals['sealion_config_file'] = get_safe_path(globals['exe_path'] + 'etc/config/sealion_config.json')
    agent_config = get_agent_config(globals['agent_config_file'])

    if agent_config == None:
        print globals['agent_config_file'] + ' is either missing or currupted'
        exit()

    agent_config['host'] = agent_config['host'].strip()
    length = len(agent_config['host'])

    if length and agent_config['host'][length - 1] == '/':
        agent_config['host'] = agent_config['host'][:-1]

    globals['agent_config'] = agent_config
    sealion_config = get_sealion_config(globals['sealion_config_file'])

    if sealion_config == None:
        print globals['sealion_config_file'] + ' is either missing or currupted'
        exit()

    globals['sealion_config'] = sealion_config
    
    if globals['agent_config'].has_key('id') == False:
        pass
    
class Singleton:    
    def __init__(self):
        if hasattr(self.__class__, '__instance') == False:
            setattr(self.__class__, '__instance', self)
        elif self.__class__ is getattr(getattr(self.__class__, '__instance'), '__class__'):
            raise RuntimeError, 'Instance already exists; use class.inst method'
        else:
            setattr(self.__class__, '__instance', self)
    
    @classmethod
    def inst(cls):
        temp = None
        
        try:
            temp = cls()
        except:
            temp = getattr(cls, '__instance')
            
        return temp
    
class Namespace:    
    def __init__(self):
        raise RuntimeError, 'Cannot instantiate class'

globals = None
init_globals()
