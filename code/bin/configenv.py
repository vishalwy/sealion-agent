#!/usr/bin/env python

"""
Provides functionality to export environment variables for agent. 
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
        
    usage_info = 'Usage: %s [options]\nOptions:\n' % sys.argv[0]
    usage_info += '      --eENVIRONMENT_VAR <arg>, ...  ENVIRONMENT_VAR to be exported\n'
    usage_info += ' -l,  --line <arg>                   Lines containing the environment variable configuration\n'
    usage_info += '      --restart                      After configuring, restart the agent\n'
    usage_info += '      --version                      Display version information\n'
    usage_info += ' -h,  --help                         Display this information\n'
    sys.stdout.write(usage_info)
    return True

def read_env_vars(lines):
    """
    Function to show usage information
    
    Args:
        lines: Lines containing the environment variable details to configure
        
    Returns:
        Environment variables dict
    """
    
    line_regex = re.compile('^[# \\t]+([a-zA-Z\\_][a-zA-Z0-9\\_]*)([ \\t]*:[ \\t]*([^ \\t\\n;]+[^\\n;]+)(;[ \\t]*(default[ \\t]+([^\\n])+|optional))?)?[ \\t]*$')
    env_vars = {}
    
    #there can be multiple lines, so loop through all of them
    for line in lines.split('\n'):
        match = line_regex.match(line)  #extract the variable details 

        #not a config
        if not match:
            continue

        match, value = match.groups(), ''
        required = False if match[4] == 'optional' else True
        default = match[5].strip() if match[5] else '' 
        prompt = '%(caption)s%(optional)s%(default)s: ' % {
            'caption': match[2].strip() if match[2] else match[0],
            'optional': ' (%s)' % match[4] if not required else '',
            'default': ' [%s]' % default if default else ''
        }

        #read the value from the terminal
        while not value:
            value = raw_input(prompt)
            value = value if value else default  #use the default value if nothing is read from the terminal

            #for a required variable continue as long as it available
            if not required:
                break

        #discard any unset variables
        if value:  
            env_vars[match[0]] = value
                
    return env_vars

try:
    env_vars, env_vars_regex, restart_agent = {}, re.compile('^--e[a-zA-Z\\_][a-zA-Z0-9\\_]*$'), False
    
    #add environment variables specified in the format --eENVIRONMENT_VAR
    #we identify them and add as long options
    long_options = [arg + '=' for arg in sys.argv[1:] if env_vars_regex.match(arg)]
    options = getopt.getopt(sys.argv[1:], 'l:h', long_options + ['line=', 'restart', 'version', 'help'])[0]
    
    for option, arg in options:        
        if option[:3] == '--e':  #environment variable
            env_vars[option[4:]] = arg
        elif option in ['-l', '--line']:  #environment variable description
            env_vars.update(read_env_vars(arg))
        elif option == '--restart':
            restart_agent = True
        elif option == '--version':
            version_info.print_version() and sys.exit(0)
        elif option in ['-h', '--help']:
            usage(True) and sys.exit(0)
            
    if not env_vars:
        sys.stderr.write('Please specify the environment variabes to configure\n')
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
    JSONfig.perform(filename = exe_path + '/etc/config.json', action = 'merge', keys = 'env', value = json.dumps(env_vars), pretty_print = True)
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

