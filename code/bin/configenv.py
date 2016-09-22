#!/usr/bin/env python

"""
Provides functionality to configure environment variables for agent. 
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys
import getopt
import re
import json
import subprocess

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/lib')
sys.path.insert(0, exe_path + '/src')

import version_info
from universal import Universal 
from constructs import unicode, read_input, JSONfig

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
        
    usage_info = 'Usage: %s [options]\nOptions:\n' % sys.argv[0]
    usage_info += '      --eENVIRONMENT_VAR <arg>, ...  ENVIRONMENT_VAR to be exported\n'
    usage_info += ' -f,  --file <arg>, ...              File containing the environment variable configuration\n'
    usage_info += '      --restart                      After configuring, restart the agent\n'
    usage_info += '      --version                      Display version information\n'
    usage_info += ' -h,  --help                         Display this information\n'
    sys.stdout.write(usage_info)
    return True

def read_env_vars(f, env_vars):
    """
    Function to show usage information
    
    Args:
        f: File descriptor containing the environment variable details to configure
        env_vars: dict representing the env vars to update
        
    Returns:
        The number of env variables parsed
    """
    
    line_regex = re.compile(r'^[# \t]+(SL\_[A-Z\_0-9]+)([ \t]*:[ \t]*([^ \t\n;]+[^\n;]*)(;[ \t]*((default[ \t]+([^ \t\n]+[^\n]*))|optional))?)?[ \t]*$')
    env_vars_count = 0
    
    #there can be multiple lines, so loop through all of them
    for line in f:
        match = line_regex.match(line)  #extract the variable details 

        #not a config
        if not match:
            continue

        match, value = match.groups(), ''
        required = False if match[4] == 'optional' else True
        default = env_vars.get(match[0], match[6].strip() if match[6] else '' )
        prompt = '%s%s: ' % (match[2].strip() if match[2] else match[0], ' (%s)' % match[4] if not required else '')
        env_vars_count += 1

        #read the value from the terminal
        while not value:
            value = read_input(prompt, default)  #use the default value if nothing is read from the terminal

            #for a required variable continue as long as it available
            if not required:
                break

        if value:  
            env_vars[match[0]] = value
        else:  #discard any unset variables
            try:
                del env_vars[match[0]]  #it could be possible the key does not even exists
            except:
                pass  
                
    return env_vars_count

try:
    #try to read the environment variables from sealion config
    env_vars = Universal().config.sealion.get_dict(('env', {}))['env']
except:
    env_vars = {}

try:
    env_vars_count, env_vars_regex, restart_agent = 0, re.compile(r'^--e[a-zA-Z\_][a-zA-Z0-9\_]*$'), False
    
    #add environment variables specified in the format --eENVIRONMENT_VAR
    #we identify them and add as long options
    long_options = [arg[2:] + '=' for arg in sys.argv[1:] if env_vars_regex.match(arg)]
    options = getopt.getopt(sys.argv[1:], 'f:h', long_options + ['file=', 'restart', 'version', 'help'])[0]
    
    for option, arg in options:        
        if option[:3] == '--e':  #environment variable
            env_vars[option[3:]] = arg
            env_vars_count += 1
        elif option in ['-f', '--file']:  #environment variable description
            with open(arg) as f:
                env_vars_count += read_env_vars(f, env_vars)
        elif option == '--restart':
            restart_agent = True
        elif option == '--version':
            version_info.print_version() and sys.exit(0)
        elif option in ['-h', '--help']:
            usage(True) and sys.exit(0)
            
    if not env_vars_count:
        sys.stderr.write('Please specify the environment variables to configure\n')
        usage() and sys.exit(1)
except getopt.GetoptError as e:
    sys.stderr.write(unicode(e).capitalize() + '\n')  #missing option value
    usage() and sys.exit(1)
except (KeyboardInterrupt, EOFError):
    sys.stdout.write('\n');
    sys.exit(0)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')  #any other exception
    sys.exit(1)
    
try:
    #perform the action
    JSONfig.perform(filename = exe_path + '/etc/config.json', action = 'set', keys = 'env', value = json.dumps(env_vars), pretty_print = True)
except KeyError as e:
    sys.stderr.write('Error: unknown key ' + unicode(e) + '\n')
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
try:
    not restart_agent and sys.exit(0)  #exit if we dont ask for restart
    subprocess.call([exe_path + '/etc/init.d/sealion', 'restart'], close_fds = True)
except Exception as e:
    sys.stderr.write('Failed to restart agent; %s\n' % unicode(e))

