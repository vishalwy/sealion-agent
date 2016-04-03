"""
Use this as the main script to run agent as a daemon.
It gives a commandline interface to the program, makes the process daemon and sets up crash dump handling.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import os
import sys
import time
import traceback
import signal
import pwd
import grp
import json
import re

#agent base directory
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]

import exit_status
from daemon import Daemon
import helper
import universal
from constructs import unicode, ThreadEx

_log = logging.getLogger(__name__)  #module level logging

def set_user(default_user_name = 'sealion'):
    """
    Function to set the user and group for the process
    
    Args:
        default_user_name: the default user name to be used in case no users found in the config
        
    Returns:
        The user name for the process
    """
    
    try:
        user_regex = universal.SealionConfig.schema['user'].get('regex')  #get the regex used for validation

        #read the user name from the config
        f = open(exe_path + '/etc/config.json', 'r')
        user_name = json.load(f)['user'];
        f.close()

        #update the user name if it is valid
        if not user_regex or re.match(user_regex, user_name):
            default_user_name = user_name
    except:
        pass

    try:
        user = pwd.getpwnam(default_user_name)  #get the pwd db entry for the user name

        #if it is not sealion user, then we need to change user and group
        #if current user is not super user, trying to change the user/group id will raise exception
        if user.pw_uid != os.getuid():
            #find all the groups where the user a member
            groups = [group.gr_gid for group in grp.getgrall() if user.pw_name in group.gr_mem and user.pw_gid != group.gr_gid]
            
            os.setgroups(groups)  #set the suplimentary groups
            os.setgid(user.pw_gid)  #set group id
            os.setuid(user.pw_uid)  #set user id
    except KeyError as e:
        sys.stderr.write('Failed to find user %s; %s\n' % (default_user_name, unicode(e)))
        sys.exit(exit_status.AGENT_ERR_FAILED_FIND_USER)
    except Exception as e:
        sys.stderr.write('Failed to change the group or user to %s; %s\n' % (default_user_name, unicode(e)))
        sys.exit(exit_status.AGENT_ERR_FAILED_CHANGE_GROUP_OR_USER)
        
    return default_user_name

class SeaLion(Daemon):
    """
    Subclass implementing agent as a daemon.
    """
    
    def __init__(self, *args, **kwargs):
        """
        Constructor.
        """
        
        Daemon.__init__(self, *args, **kwargs)  #initialize the base class
        self.crash_loop_timeout = 30  #timeout between each crash and resurrect
        self.crash_loop_count = 5  #count of crash dumps to determine crash loop
        self.crash_dump_path = '%s/var/crash/' % exe_path  #crash dump path
        self.crash_dump_pattern = '^sealion-%s-[0-9]+\.dmp$'
        self.agent_version_regex = '(\d+\.){2}\d+(\.[a-z0-9]+)?'
    
    def save_dump(self, stack_trace):
        """
        Method to save the stack trace as a crash dump.
        
        Args:
            stack_trace: stack trace of exception.
            
        Returns:
            Path to the crash dump on success else False
        """
        
        univ = universal.Universal()  #get Universal
        timestamp = int(time.time() * 1000)  #timestamp for the unique crash dump filename
        path = self.crash_dump_path + ('sealion-%s-%d.dmp' % (univ.config.agent.agentVersion, timestamp))  #crash dump filename
        f = None
        
        try:
            helper.Utils.get_safe_path(path)  #create dump directory if it is not available
            
            #dict continaing crash dump details
            report = {
                'timestamp': timestamp,
                'stack': stack_trace,
                'orgToken': univ.config.agent.orgToken,
                '_id': univ.config.agent.get(['config', '_id']),
                'os': {'pythonVersion': univ.details['pythonVersion']},
                'process': {
                    'uid': os.getuid(),
                    'gid': os.getgid(),
                    'uptime': int(univ.get_run_time() * 1000),
                    'agentVersion': univ.config.agent.agentVersion,
                    'isProxy': univ.details['isProxy']
                }
            }
            
            #write dump
            f = open(path, 'w')
            json.dump(report, f)
        except:
            return None
        finally:
            f and f.close()
        
        return path
    
    def read_dump(self, filename):
        """
        Method to read the crash dump.
        
        Args:
            filename: crash dump file
            
        Returns:
            Dict containing crash dump details on success, else None
        """
        
        f, report = None, None
        keys = ['timestamp', 'stack', 'orgToken', '_id', 'os', 'process']  #keys for valid crash dump
        
        try:
            #read the dump
            f = open(filename, 'r')
            report = json.load(f)
        except:
            pass
        finally:
            f and f.close()
            
        if report == None or all(key in report for key in keys) == False:  #validate the dict
            report = None
        
        return report
    
    def send_crash_dumps(self):
        """
        Method to send all crash dumps to server.
        This method runs in a seperate thread.
        """
        
        import api
        univ = universal.Universal()  #get Universal
        
        #how much time the crash dump sender wait before start sending.
        #this is required not to affect crash loop detection, since crash loop detection is done by checking number crash dumps generated in a span of time
        crash_dump_timeout = (self.crash_loop_count * self.crash_loop_timeout) + 10 
        
        _log.debug('CrashDumpSender waiting for stop event for %d seconds' % crash_dump_timeout)
        univ.stop_event.wait(crash_dump_timeout)
        
        try:
            for file in os.listdir(self.crash_dump_path):  #loop though files in the crash dump directory
                file_name = self.crash_dump_path + file

                #is this a valid crash dump filename
                if os.path.isfile(file_name) and re.match(self.crash_dump_pattern % self.agent_version_regex, file) != None:
                    report = None

                    while 1:
                        if univ.stop_event.is_set():  #do we need to stop now
                            _log.debug('CrashDumpSender received stop event')
                            return

                        #read the report from the dump, or retry the report
                        report = report if report != None else self.read_dump(file_name)

                        if report == None or api.is_not_connected(api.unauth_session.send_crash_report(report)) == False:  #send the dump
                            break

                        _log.debug('CrashDumpSender waiting for stop event for 10 seconds')
                        univ.stop_event.wait(10)  #on failure, wait for some time
                    
                    try:
                        os.remove(file_name)  #remove the dump as we sent it
                        _log.info('Removed dump %s' % file_name)
                    except Exception as e:
                        _log.error('Failed to remove dump %s; %s' % (file_name, unicode(e)))

                if univ.stop_event.is_set():  #do we need to stop now
                    _log.debug('CrashDumpSender received stop event')
                    return
        except:
            pass
    
    def set_procname(self, proc_name = None):
        """
        Method to set the process name to show in 'top' command output.
        """
        
        proc_name = proc_name if proc_name else self.daemon_name
        
        try:
            from ctypes import cdll, byref, create_string_buffer
            libc = cdll.LoadLibrary('libc.so.6')
            buff = create_string_buffer(len(proc_name) + 1)
            buff.value = proc_name.encode('utf-8')
            libc.prctl(15, byref(buff), 0, 0, 0)
        except Exception as e:
            _log.error('Failed to set process name; %s' % unicode(e))
        
    def initialize(self):        
        """
        Method to perform some tasks before daemonizing. The idea is to throw any error before daemonizing.
        """
        
        set_user()  #set the user and group for the current process
                
        try:
            #try to create pid file
            helper.Utils.get_safe_path(self.pidfile)
            f = open(self.pidfile, 'w');
            f.close()
        except Exception as e:
            sys.stderr.write(unicode(e) + '\n')
            sys.exit(exit_status.AGENT_ERR_FAILED_PID_FILE)
        
        import main  #import main module so that we get any error before daemonizing
        sys.excepthook = self.exception_hook  #set the exception hook so that we can generate crash dumps
        
    def get_crash_dump_details(self):
        """
        Method to get crash dump count. It also reports any crash loop by examining the file timestamp.
        
        Returns:
            Tupple (is crah loop, crash dump count)
        """
        
        univ = universal.Universal()  #get Universal
        t = int(time.time())  #current epoch time for crash loop detection
        crash_loop_timeout = self.crash_loop_count * self.crash_loop_timeout  #time span for crash loop detection
        file_count, loop_file_count = 0, 0
        
        #crash loop is detected only for the current agent version running
        loop_regex = self.crash_dump_pattern % univ.config.agent.agentVersion.replace('.', '\.')
        
        try:
            for f in os.listdir(self.crash_dump_path):  #loop though files in the crash dump directory
                #if it is a valid crash dump file name
                if os.path.isfile(self.crash_dump_path + f) and re.match(self.crash_dump_pattern % self.agent_version_regex, f) != None:
                    file_count += 1
                    
                    #is this file contribute to crash loop
                    if re.match(loop_regex, f) != None and t - os.path.getmtime(self.crash_dump_path + f) < crash_loop_timeout:
                        loop_file_count += 1
        except:
            pass
        
        return (loop_file_count >= 5, file_count)
        
    def exception_hook(self, type, value, tb):
        """
        Method gets called whenever an unhandled exception is raised.
        The method restarts the agent by passing the stack trace.
        """
        
        if type != SystemExit:  #filter out sys.exit()
            import helper
            trace = helper.Utils.get_stack_trace(''.join(traceback.format_exception(type, value, tb)))
            helper.Utils.restart_agent('%s crashed' % self.daemon_name, trace)
    
    def run(self):
        """
        Method runs in the daemon.
        """
        
        self.set_procname(self.daemon_name + ('d' if self.daemon_name[-1] != 'd' else ''))  #set process name for display purpose
        is_update_only_mode = False
        crash_dump_details = self.get_crash_dump_details()  #get crash dump details
        helper.terminatehook = self.termination_hook  #set the termination hook called whenever agent shutdown disgracefully
        
        if crash_dump_details[1] > 0:  #start thread to send crash dump
            _log.info('Found %d dumps' % crash_dump_details[1])
            ThreadEx(target = self.send_crash_dumps, name = 'CrashDumpSender').start()
        
        if crash_dump_details[0] == True:  #crash loop detected. start agent in update only mode
            _log.info('Crash loop detected; Starting agent in update-only mode')
            is_update_only_mode = True
        
        import main
        main.stop_stream_logging()  #stop logging on stdout/stderr
        main.run(is_update_only_mode)  #start executing agent
        
    def termination_hook(self, message, stack_trace):
        """
        Termination hook for disgraceful shutdown.
        
        Args:
            message: message to be logged
            stack_trace: stack trace to be dumped
        """
        
        self.cleanup()
        message and _log.error(message)
        
        if stack_trace:  #save the stack trace if any
            dump_file = self.save_dump(stack_trace)

            if dump_file:
                _log.info('Dump file saved at %s' % dump_file)
            else:
                _log.info('Failed to save dump file')
            
def sigint_handler(*args):    
    """
    Callback function to handle SIGINT signal.
    """
    
    sys.exit(exit_status.AGENT_ERR_INTERRUPTED)
        
def run():
    """
    Function to run the module.
    """
    
    signal.signal(signal.SIGINT, sigint_handler)  #setup signal handling for SIGINT
    daemon = SeaLion(exe_path + '/var/run/sealion.pid')  #SeaLion daemon instance
    valid_usage = ['start', 'stop', 'restart', 'status']

    #perform the operation based on the commandline
    #do not call getattr directly without validating as it will allow any method inside the daemon to run
    if len(sys.argv) == 2 and sys.argv[1] in valid_usage:
        getattr(daemon, sys.argv[1])()
    else:
        len(sys.argv) > 1 and sys.stderr.write('Invalid usage: \'%s\'\n' % ' '.join(sys.argv[1:]))
        sys.stdout.write('Usage: %s %s\n' % (daemon.daemon_name, '|'.join(valid_usage)))

    sys.exit(exit_status.AGENT_ERR_SUCCESS)
