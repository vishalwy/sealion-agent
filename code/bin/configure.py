#!/usr/bin/env python

"""
Provides functionality to manipulate JSON files. 
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import json

#Python 2.x vs 3.x
try:
    t_unicode = unicode
except:
    def unicode_3_x(object, *args, **kwargs):
        return str(object)
    
    t_unicode = unicode_3_x
    
unicode = t_unicode  #export symbol unicode

def get_value(obj, key):
    """
    Function gets the value for the key from the dict given
    
    Args:
        obj: the dict from which the value to be extracted
        key: key for the value
        
    Returns:
        Value for the key specified
    """
    
    if type(obj) is list:
        items = [item for item in obj if type(item) is dict and item.get(key) is not None]

        if not len(items):
            raise KeyError(key)

        return items[0][key]
    
    return obj[key]

def set_value(obj, key, value):
    """
    Function sets the value for the key from the dict given
    
    Args:
        obj: the dict for which the value to be set
        key: key for the value
    """
    
    if type(obj) is list:
        items = [item for item in obj if type(item) is dict and item.get(key) is not None]
        
        if not len(items):
            raise KeyError(key)
        
        items[0][key] = value
    else:
        obj[key] = value;

actions = ['get', 'set', 'add', 'rem', 'del']  #possible operations on the JSON file
usage = 'Usage: configure.py {-k <key1[:key2[:key3[:...]]> [-a <%s>] [-v <value>] [-n] <JSON file> | -h for Help}\n' % '|'.join(actions)
keys, value, action, pretty_print, file, i, arg_len = None, None, 'get', True, None, 1, len(sys.argv)

try:
    while i < arg_len:  #read all the arguments
        arg = sys.argv[i]

        if arg[:1] == '-':  #considering single letter options only
            if arg == '-k':  #key
                i += 1  #read option value
                keys = sys.argv[i]
            elif arg == '-v':  #value for the key
                i += 1  #read option value
                value = sys.argv[i]  #set the value
            elif arg == '-n':  #do not pretty print while writing to file
                pretty_print = False
            elif arg == '-a':  #operation to be performed; default to 'get'
                i += 1  #read option value
                
                if sys.argv[i] in actions:
                    action = sys.argv[i]  #set the action
                else:
                    sys.stderr.write('Error: uknown argument \'%s\' for %s\n%s' % (sys.argv[i], arg, usage))  #unknown action value
                    sys.exit(1)
            elif arg == '-h':
                sys.stdout.write(usage)
                sys.exit(0)
        else:  #anything else is considered as the file to read
            file = arg.strip()
            
        i += 1  #next option
except IndexError:
    sys.stderr.write('Error: %s requires an argument\n%s' % (sys.argv[i - 1], usage))  #missing option value
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')  #any other exception
    sys.exit(1)
    
if keys == None:  #no keys specified for the operation
    sys.stderr.write('Error: please specify a key\n%s' % usage)
    sys.exit(1)
    
if value == None and action != 'get' and action != 'del':  #any action other than get and del requires a value to be set
    sys.stderr.write('Error: please specify a value to %s\n%s' % (action, usage))
    sys.exit(1)
    
if not(file):  #no file specified
    sys.stderr.write('Error: please specify a file to read/write\n%s' % usage)
    sys.exit(1)
    
try:
    try:
        f = open(file, 'r')
        data = json.load(f)
        f.close()
    except (IOError, ValueError) as e:
        if action == 'get':  #ignore exceptions raised by the absense of JSON object if the action implies a write operation
            raise e
        
        data = {}  #no JSON available
    
    temp_data = data   
    keys = keys.split(':')  #format of the key is decided by the heirarchy; for eg, 'logging:level'

    for key in keys[:-1]:  #navigate the frist key from the last, this is required so that we can have proper reference
        temp_data = get_value(temp_data, key)
        
    if action == 'get':  #print the data in stdout in json format
        if len(keys) == 1 and keys[0] == '':
            sys.stdout.write(json.dumps(data, indent = 4) + '\n')
        else:
            sys.stdout.write(json.dumps(get_value(temp_data, keys[-1]), indent = 4) + '\n')
            
        sys.exit(0)
    elif action == 'set':  #set the value
        if len(keys) == 1 and keys[0] == '':
            data = json.loads(value)
        else:
            set_value(temp_data, keys[-1], json.loads(value))
    elif action == 'add':  #add a new value in the array
        temp_value = json.loads(value)
        temp_data_value = get_value(temp_data, keys[-1])
        
        if type(temp_value) is list:
            for i in list(range(len(temp_value))):
                temp_value[i] not in temp_data_value and temp_data_value.append(temp_value[i])
        else:
            if temp_value in temp_data[keys[-1]]:
                raise ValueError('list.append(x): x is already in the list')
            
            temp_data_value.append(temp_value)
    elif action == 'rem':  #remove a value from the array
        temp_value = json.loads(value)
        temp_data_value = get_value(temp_data, keys[-1])
        
        if type(temp_value) is list:
            for i in list(range(len(temp_value))):
                temp_value[i] in temp_data_value and temp_data_value.remove(temp_value[i])
        else:
            temp_data_value.remove(temp_value)
    else:
        del temp_data[keys[-1]]  #delete the key
    
    #write JSON to file
    f = open(file, 'w')
    json.dump(data, f, indent = 4 if pretty_print else None)
    f.close()
except KeyError as e:
    sys.stderr.write('Error: unknown key ' + unicode(e) + '\n')
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
sys.exit(0)
    
