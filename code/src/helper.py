import os.path
import os
import sys

def is_success(response):
    return True if (response.status_code == 304 or (response.status_code >= 200 and response.status_code < 300)) else False

def get_complete_url(url, is_socket_io = False):
    base_url = 'https://api-rituparna.sealion.com' + ('' if is_socket_io else '/agents')
    base_url = base_url if url[0] == '/' else (base_url + '/')
    base_url = base_url + ('' if is_socket_io else url)
    return base_url

def sanitize_dict(d, must_keys = [], optional_keys = [], is_delete_extra = True, callback = None):
    temp_must_keys, temp_optional_keys = [], []
    new_dict = {}
    
    for key in d: 
        temp = []
        is_must_keys = True
        temp = [item for item in must_keys if item[0] == key]
        
        if len(temp) == 0:
            is_must_keys = False
            temp = [item for item in optional_keys if item[0] == key]
                
        if len(temp):
            t1 = type(d[key])
            t2 = type(d[key]) if len(temp[0]) < 2 else temp[0][1]
            
            if t1 is t2:
                new_dict[key] = d[key]
                
                if is_must_keys == True:
                    temp_must_keys.append(key)
                else:
                    temp_optional_keys.append(key)
                    
                if t1 is list and type(callback) is function:
                    new_dict[key] = []
                    
                    for i in range(0, len(d[key])):
                        if callback(new_dict[key][i], is_delete_extra) == False:
                            new_dict[key][i]
                elif t1 is dict and type(callback) is function:
                    new_dict[key] = callback(new_dict[key], is_delete_extra)
        elif is_delete_extra != True:
            new_dict[key] = d[key]
            
    d.clear()
    d.update(new_dict)
    
    ret = {
        'dict': d,
        'must_keys': temp_must_keys,
        'optional_keys': temp_optional_keys
    }
    
    return ret

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
                value = json.load(data)
        except:
            pass
    
    return value

def get_agent_config(file, is_data = False):
    must_keys =  [('host', 'str'), ('token', 'str')]
    optional_keys = [('id', 'str'), ('version', 'str')]
    ret = sanitize_dict(get_config(file, is_data), must_keys, optional_keys)
        
    if ret[2] != 2:
        if ret[0].has_key('id'):
            del ret[0]['id']
            
        if ret[0].has_key('version'):
            del ret[0]['version']
            
    if ret[1] != 2:
        return None
    
    return ret[0]

def get_sealion_config(file, is_data = False):
    optional_keys = [('proxy', 'dict'), ('version', 'str')]
    ret = sanitize_dict(get_config(file, is_data), [], optional_keys)
        
    if ret[2] != 2:
        if ret[0].has_key('id'):
            del ret[0]['id']
            
        if ret[0].has_key('version'):
            del ret[0]['version']
            
    if ret[1] != 2:
        return None
    
    return ret[0]

globals = {}
globals['exe_path'] = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
globals['exe_path'] = globals['exe_path'] if (globals['exe_path'][len(globals['exe_path']) - 1] == '/') else (globals['exe_path'] + '/')
globals['lock_file'] = get_safe_path(globals['exe_path'] + 'var/run/sealion.pid')
globals['agent_config_file'] = get_safe_path(globals['exe_path'] + 'etc/config/agent_config.json')
globals['sealion_config_file'] = get_safe_path(globals['exe_path'] + 'etc/config/sealion_config.json')

agent_config = get_agent_config(globals['agent_config_file'])

if agent_config == None:
    print 'Missing or currupted config file'
    exit()
    
globals['agent_config'] = agent_config




