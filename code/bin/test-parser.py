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
    usage_info += '      --version   Display version information\n'
    usage_info += ' -h,  --help      Display this information\n'
    usage_info += """
The directory should contain the commands and metrics in the following structure.

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
"""

    sys.stdout.write(usage_info)
    return True

def execute(file):
    global process
    output, status = '', 0
    
    try:
        log.debug('$> ./%s' % file)
        process = subprocess.Popen(['bash', file], bufsize = 0, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        output = process.communicate()[0]
        log.debug('%s' % output)
    except:
        pass
    
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
    
    process and process.poll() == None and process.kill()
    os._exit(0)

def main(directory):
    signal.signal(signal.SIGQUIT, sigquit_handler)
    sys.stderr = sys.stdout
    logging.basicConfig(level = logging.DEBUG, format = '%(message)s') 
    service.set_user()
    univ, seperator = universal.Universal(), '\n'
    os.environ.update(univ.config.sealion.get_dict((['config', 'envVariables'], {}))['envVariables'])
    os.environ.update(univ.config.sealion.get_dict(('env', {}))['env'])
    
    try:
        os.chdir(os.path.realpath(directory))
        log.debug('SIGQUIT(Ctrl-\\) to exit; SIGINT(Ctrl-C) to abort current operation')
        log.debug('Working directory: %s' % os.path.realpath(directory))
        
        for activity in os.listdir('./'):
            try:
                if activity[-3:] != '.sh' or not os.path.isfile(activity):
                    continue

                seperator and log.debug(seperator)
                output, status = execute(activity)
                
                if not output:
                    continue
                    
                metrics = {}
                
                for metric in os.listdir(activity[:-3]):
                    try:
                        if metric[-3:] != '.py':
                            continue

                        with open(activity[:-3] + '/' + metric) as f:
                            metrics[metric] = {'parser': f.read()}
                    except:
                        pass
                    
                extract.extract_metrics(output, status, metrics, activity)
                seperator = '%s\n' % ('_' * 50)
            except:
                pass
    except Exception as e:
        log.error('Error: %s', unicode(e))
        
        
try:
    options, args = getopt.getopt(sys.argv[1:], 'h', ['version', 'help'])
    
    for option, arg in options:
        if option == '--version':
            version_info.print_version() and sys.exit(0)
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
    
main(directory)
