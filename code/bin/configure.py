#!/usr/bin/env python

"""
Provides functionality to manipulate JSON files. 
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import json
import getopt

#Python 2.x vs 3.x
try:
    t_unicode = unicode
except:
    def unicode_3_x(object, *args, **kwargs):
        return str(object)
    
    t_unicode = unicode_3_x
    
unicode = t_unicode  #export symbol unicode

def usage(is_help = False):
    """
    Function to show usage information
    
    Args:
        is_help: Whether to show the full help or just the command to show help
        
    Returns:
        True
    """
    
    if is_help == False:
        sys.stdout.write('Run \'%s --help\' for more information\n' % sys.argv[0])
        return True
        
    usage = 'Usage: %s [options] <JSON config file>\nOptions:\n' % sys.argv[0]
    usage += ' -a,\t--action <arg>    \tOperation to be performed; %s\n' % '|'.join(actions)
    usage += ' -k,\t--key <arg>       \tKey to be looked up; It should be in the form \'key1:key2:key3\' based on the heirarchy\n'
    usage += '                        \tSupply empty key \'\' to read the whole JSON\n'
    usage += ' -v,\t--value <arg>     \tJSON document representing the value to be used for write operations\n'
    usage += ' -n,\t--no-pretty-print \tDo not pretty print while writing to the file; Pretty print is ON by default\n'
    usage += ' -h,\t--help            \tDisplay this information\n'
    sys.stdout.write(usage)
    return True

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
keys, value, action, pretty_print, file = None, None, 'get', True, None

try:
    options, args = getopt.getopt(sys.argv[1:], 'k:v:a:nh', ['key=', 'value=', 'action=', 'no-pretty-print', 'help'])
    
    for option, arg in options:        
        if option in ['-k', '--key']:  #key
            keys = arg
        elif option in ['-v', '--value']:  #value for the key
            value = arg  #set the value
        elif option in ['-n', '--no-pretty-print']:  #do not pretty print while writing to file
            pretty_print = False
        elif option in ['-a', '--action']:  #operation to be performed; default to 'get'
            if arg in actions:
                action = arg  #set the action
            else:
                sys.stderr.write('Uknown argument \'%s\' for %s\n' % (arg, option))  #unknown action
                usage() and sys.exit(1)
        elif option in ['-h', '--help']:
            usage(True) and sys.exit(0)
        else:  #anything else is considered as the file to read
            file = arg.strip()
    
    file = args[-1] if args else file
except getopt.GetoptError as e:
    sys.stderr.write(unicode(e).capitalize() + '\n')  #missing option value
    usage() and sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')  #any other exception
    sys.exit(1)
    
if keys == None:  #no keys specified for the operation
    sys.stderr.write('Please specify a key\n')
    usage() and sys.exit(1)
    
if value == None and action != 'get' and action != 'del':  #any action other than get and del requires a value to be set
    sys.stderr.write('Please specify a value to %s\n' % action)
    usage() and sys.exit(1)
    
if not file:  #no file specified
    sys.stderr.write('Please specify a file to read/write\n')
    usage() and sys.exit(1)
    
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
    
