#!/usr/bin/env python

"""
Provides functionality to manipulate JSON files. 
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys
import getopt

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/lib')
sys.path.insert(0, exe_path + '/src')

import version_info
from constructs import unicode, JSONfig

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
        
    usage_info = 'Usage: %s [options] <JSON config file>\nOptions:\n' % sys.argv[0]
    usage_info += ' -a,  --action <arg>      Operation to be performed; %s; default to \'get\'\n' % '|'.join(JSONfig.actions)
    usage_info += ' -k,  --key <arg>         Key to be looked up; it should be in the form \'key1:key2:key3\' based on the heirarchy\n'
    usage_info += '                          Supply empty key \'\' to read the whole JSON\n'
    usage_info += ' -v,  --value <arg>       JSON document representing the value to be used for write operations\n'
    usage_info += ' -n,  --no-pretty-print   Do not pretty print the output; pretty print is ON by default\n'
    usage_info += '      --version           Display version information\n'
    usage_info += ' -h,  --help              Display this information\n'
    sys.stdout.write(usage_info)
    return True

keys, value, action, pretty_print, filename = None, None, 'get', True, None

try:
    options, args = getopt.getopt(sys.argv[1:], 'k:v:a:nh', ['key=', 'value=', 'action=', 'no-pretty-print', 'version', 'help'])
    
    for option, arg in options:        
        if option in ['-k', '--key']:  #key
            keys = arg
        elif option in ['-v', '--value']:  #value for the key
            value = arg  #set the value
        elif option in ['-n', '--no-pretty-print']:  #do not pretty print while writing to file
            pretty_print = False
        elif option in ['-a', '--action']:  #operation to be performed; default to 'get'
            if arg in JSONfig.actions:
                action = arg  #set the action
            else:
                sys.stderr.write('Uknown argument \'%s\' for %s\n' % (arg, option))  #unknown action
                usage() and sys.exit(1)
        elif option == '--version':
            version_info.print_version() and sys.exit(0)
        elif option in ['-h', '--help']:
            usage(True) and sys.exit(0)
        else:  #anything else is considered as the file to read
            filename = arg.strip()
    
    filename = args[-1] if args else filename
except getopt.GetoptError as e:
    sys.stderr.write(unicode(e).capitalize() + '\n')  #missing option value
    usage() and sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')  #any other exception
    sys.exit(1)
    
if keys == None:  #no keys specified for the operation
    sys.stderr.write('Please specify a key\n')
    usage() and sys.exit(1)
    
if value == None and action not in ['get', 'delete']:  #any action other than get and del requires a value to be set
    sys.stderr.write('Please specify a value to %s\n' % action)
    usage() and sys.exit(1)
    
if not filename:  #no file specified
    sys.stderr.write('Please specify a file to read/write\n')
    usage() and sys.exit(1)
    
try:
    #perform the action and print any output produced
    dump = JSONfig.perform(filename = filename, action = action, keys = keys, value = value, pretty_print = pretty_print)
    dump and sys.stdout.write(dump + '\n')
except KeyError as e:
    sys.stderr.write('Error: unknown key ' + unicode(e) + '\n')
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
sys.exit(0)
    
