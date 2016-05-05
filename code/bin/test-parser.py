#!/usr/bin/env python

"""
Script to test the parser.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os
import subprocess
import logging
import signal
import getopt

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/lib')
sys.path.insert(0, exe_path + '/src')

import version_info
import universal
import service
import extract
from constructs import unicode

log, process = logging.getLogger(__name__), None

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
         
    usage_info = 'Usage: %s [options] <directory>\nOptions:\n' % sys.argv[0]
    usage_info += ' -i,  --interval   Command interval; default to 60 seconds\n'
    usage_info += '      --version    Display version information\n'
    usage_info += ' -h,  --help       Display this information\n'
    usage_info += """\nThe directory should contain the commands and metrics in the following structure.

    directory/
        |- command-1.sh
        |- command-1/
        |    |- metric-1a.py
        |    |- metric-1b.py
        |    :
        |    |- metric-1z.py
        |- command-2.sh
        |- command-2/
        |    |- metric-2a.py
        |    |- metric-2b.py
        |    :
        |    |- metric-2z.py
        :
        |- command-N.sh
        |- command-N/
             |- metric-Na.py
             |- metric-Nb.py
             :
             |- metric-Nz.py
    \n"""

    sys.stdout.write(usage_info)
    return True

def execute(file):
    """
    Function to execute the bash script given
    
    Args:
        file: path to the file containing bash script
        
    Returns:
        tupple containing the output and the exit status of the script
    """
    
    global process  #use the global process handler so that the other function can operate on it
    output, status = '', 0
    
    try:
        log.debug('$> ./%s' % file)
        
        #execute the script and get the output
        process = subprocess.Popen(['bash', file], bufsize = 0, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        output = process.communicate()[0]  
        
        log.debug('%s' % output)
    except:
        pass
    
    #terminate the process if it is still running
    #this is required if any exception is raised during the execution, say KeyboardInterrupt
    process.poll() == None and process.kill()
    process.wait()
    
    status = process.returncode;
    process = None
    log.debug('Process finished with status code %d' % status)
    return output, status

def sigquit_handler(*args):    
    """
    Callback function to handle SIGQUIT signal.
    """
    
    process and process.poll() == None and process.kill()  #terminate the process if it is running
    os._exit(0)  #exit without calling exit handlers

def main(directory, command_interval):
    signal.signal(signal.SIGQUIT, sigquit_handler)  #install SIGQUIT handler so that the program can stop
    sys.stderr = sys.stdout  #as we are using log module and we want the output to be in stdout, redirect
    logging.basicConfig(level = logging.DEBUG, format = '%(message)s') 
    service.set_user()  #set the user and group for the process
    univ, seperator = universal.Universal(), '\n'
    
    #export the environment variables
    os.environ.update(univ.config.sealion.get_dict((['config', 'envVariables'], {}))['envVariables'])
    os.environ.update(univ.config.sealion.get_dict(('env', {}))['env'])
    os.environ.update({'COMMAND_INTERVAL': unicode(command_interval)})
    
    try:
        os.chdir(os.path.realpath(directory))
        log.debug('SIGQUIT(Ctrl-\\) to exit; SIGINT(Ctrl-C) to abort current operation')
        log.debug('Working directory: %s' % os.path.realpath(directory))
        
        #loop through the content of the directory
        for activity in os.listdir('./'):
            try:
                #consider only *.sh files
                if activity[-3:] != '.sh' or not os.path.isfile(activity):
                    continue

                seperator and log.debug(seperator)
                output, status = execute(activity)  #execute and get the output
                
                if not output:
                    continue
                    
                metrics = {}
                
                #loop through the contents of the metric folder for the activity
                for metric in os.listdir(activity[:-3]):
                    try:
                        #consider only *.py files
                        if metric[-3:] != '.py':
                            continue

                        #read the parser code from the file
                        with open(activity[:-3] + '/' + metric) as f:
                            metrics[metric] = {'parser': f.read()}
                    except:
                        pass
                    
                extract.extract_metrics(output, status, metrics, activity)  #extract metrics
                seperator = '%s\n' % ('_' * 50)
            except:
                pass
    except Exception as e:
        log.error('Error: %s', unicode(e))
        
        
try:
    options, args = getopt.getopt(sys.argv[1:], 'i:h', ['interval=', 'version', 'help'])
    command_interval = 60  #default command interval 
    
    for option, arg in options:
        if option == '--version':
            version_info.print_version() and sys.exit(0)
        elif option in ['-i', '--interval']:
            command_interval = int(arg)
        elif option in ['-h', '--help']:
            usage(True) and sys.exit(0)
        
    directory = args[-1].strip() if args else ''
except getopt.GetoptError as e:
    sys.stderr.write(unicode(e).capitalize() + '\n')  #missing option value
    usage() and sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
if not directory:  #no directory specified
    sys.stderr.write('Please specify a directory to test\n')
    usage() and sys.exit(1)
    
main(directory, command_interval)
