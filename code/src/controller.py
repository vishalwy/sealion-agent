"""
The module that controls the execution of agent.
Implements Controller, dump_stack_traces and run
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import subprocess
import logging
import threading
import subprocess
import signal
import sys
import os
import time
import api
import rtc
import storage
import universal
import connection
import services
import exit_status
import helper
from constructs import *

_log = logging.getLogger(__name__)  #module level logging
_active_signals = {}

class Controller(SingletonType('ControllerMetaClass', (ThreadEx, ), {})):    
    """
    Singlton implementation of controller thread
    """
    
    def __init__(self):
        """
        Constructor
        """
        
        ThreadEx.__init__(self)  #initialize the base class
        self.univ = universal.Universal()  #save the reference to Universal for optimized access
        self.is_stop = False  #flag determines to stop the execution of controller
        self.main_thread = threading.current_thread()  #reference for main thread
        self.updater = None  #updater thread
        self.updater_lock = threading.RLock()  #thread lock for updating agent
    
    def handle_response(self, status):
        """
        Method to handle the api session response.
        
        Args:
            status: status of the request to be handled
            
        Returns:
            True if the response is ok, else False
        """
        
        _log.debug('Handling response status %d' % status)
        
        if status == api.Status.SUCCESS:  #all good
            return True
        elif api.is_not_connected(status):
            _log.info('Failed to establish connection')
        elif status == api.Status.NOT_FOUND:  #uninstall if the agent is not found in the organization
            try:
                _log.info('Uninstalling agent')
                subprocess.Popen([self.univ.exe_path + 'uninstall.sh'])
            except Exception as e:
                _log.error('Failed to open uninstall script; %s' % unicode(e))
        elif status == api.Status.UNAUTHORIZED:
            _log.error('Agent unauthorized to connect')
        elif status == api.Status.BAD_REQUEST:
            _log.error('Server marked the request as bad')
        elif status == api.Status.SESSION_CONFLICT:
            _log.error('Agent session conflict')

        return False
    
    @staticmethod
    def is_rtc_heartbeating():
        """
        Static function to check whether socket-io is alive.
        
        Returns:
            True if alive else False
        """
        
        if api.session.is_authenticated() == False:  #an unauthorized session will not have socket-io running
            return True
        
        if rtc.session == None:  #socket-io is yet to initialize
            return True  #consider it as ok
        else:
            ret = rtc.session.is_heartbeating()  #check heartbeat
            ret == False and rtc.session.update_heartbeat()
            return ret
        
    def update_agent(self, *args, **kwargs):
        """
        Method to update the agent.
        It is also bind to the global event dispatcher for 'update-agent' event, so that other modules can invoke it
        """
        
        self.updater_lock.acquire()  #this has to be atomic as mulriple threads read/write
        
        try:
            if self.updater != None:  #if an updater thread already running
                return

            self.updater = True  #assign non None, so that any other thread will immediately return
            version_details = api.unauth_session.get_agent_version()  #get the available version details for the agent

            if type(version_details) is dict and version_details['agentVersion'] != self.univ.config.agent.agentVersion:  #match version
                self.updater = ThreadEx(target = self.install_update, name = 'Updater', args = (version_details,))  #thread to perform update

                #we should run the updater thread as daemon, because the update script first terminates the agent
                #python process wont exit untill all the non-daemon threads are terminated, and if it is non-daemon, it will deadlock
                self.updater.daemon = True 
                self.updater.start()
            else:
                self.updater = None  #reset the member so that another update can run
        finally:
            self.updater_lock.release()
            
    def install_update(self, version_details):
        """
        Method to install update. This is the thread target for updating agent.
        
        Args:
            version_details: version details for the update
        """
        
        _log.info('Update found; Installing update version %s' % version_details['agentVersion'])
        curllike = self.univ.exe_path + 'bin/curlike.py'  #curl like functionality
        url_caller = '"%s" "%s"' % (sys.executable, curllike)  #commandline for curlike.py
        
        #frame the full commandline to download and execute the curl-install.sh
        format = '%(url_caller)s -s %(proxy)s %(download_url)s | bash /dev/stdin -a %(agent_id)s -o %(org_token)s -i "%(exe_path)s" -p "%(executable)s" -v %(version)s %(proxy)s'
        format_spec = {
            'url_caller': url_caller,
            'exe_path': self.univ.exe_path, 
            'executable': sys.executable, 
            'org_token': self.univ.config.agent.orgToken, 
            'agent_id': self.univ.config.agent._id,
            'version': version_details['agentVersion'], 
            'download_url': self.univ.get_url().replace('://api', '://agent'),
            'proxy': ('-x "%s"' % self.univ.proxy_url) if self.univ.details['isProxy'] else ''
        }
            
        try:
            f = open(curllike)  #check we have curllike
            f.close()
            
            #export 'URL_CALLER' environment variable for curl-install.sh to use
            environ = {}
            environ.update(os.environ)
            environ['URL_CALLER'] = url_caller
            
            subprocess.call(['bash', '-c', format % format_spec], preexec_fn = os.setpgrp, env = environ)  #execute the commandline
            time.sleep(5)  #it will not reach here if the update was successful
            raise Exception('')  #raise an exception to indicate failed update
        except Exception as e:
            error = unicode(e)
            error = '; ' + error if error else ''
            _log.error('Failed to install update version %s%s' % (version_details['agentVersion'], error))
        
        self.updater = None  #reset the member so that another update can run
        
    def exe(self):        
        """
        Method that runs in the new thread.
        """
        
        while 1:  #process continuously
            if self.univ.is_update_only_mode == True:  #in update only mode, all we have to check is an update is available
                self.update_agent()
                
                #wait for some time
                _log.debug('%s waiting for stop event for %d seconds' % (self.name, 5 * 60, ))
                self.univ.stop_event.wait(5 * 60)

                if self.univ.stop_event.is_set():  #do we need to stop here
                    _log.debug('%s received stop event', self.name)
                    self.univ.set_time_metric('stopping_time')
                    break
                elif self.univ.get_run_time() >= 30 * 60:  #restart if total running time in update only mode is more that 30 mins,
                    helper.Utils.restart_agent('No updates available')
            else:
                self.univ.event_dispatcher.bind('update_agent', self.update_agent)  #bind to 'update_agent' event
                
                if self.handle_response(connection.Connection().connect()) == False:  #if authontication fails
                    self.univ.set_time_metric('stopping_time')
                    break
                    
                store = storage.Storage()  #Storage instance
                job_producer = services.JobProducer(store)  #JobProducer instance

                if store.start() == False:  #try to start the store
                    self.univ.set_time_metric('stopping_time')
                    break
                    
                job_producer.start()  #start job producer

                while 1:              
                    if Controller.is_rtc_heartbeating() == False:  #check socket-io heartbeat. if it is not beating we need to call the config
                        api.session.get_config()
                    
                    finished_job_count = 0  #count of finished jobs in this iteration

                    #get the finished jobs and push the data
                    for job in job_producer.executer.finish_jobs():
                        store.push(job.exec_details['_id'], job.get_data())
                        finished_job_count += 1

                    finished_job_count and _log.debug('Finished execution of %d activities' % finished_job_count)
                    self.univ.stop_event.wait(5)  #wait for the stop event for sometime before next iteration

                    if self.univ.stop_event.is_set():
                        _log.debug('%s received stop event', self.name)
                        self.univ.set_time_metric('stopping_time')
                        break
                        
                self.handle_response(api.session.stop_status)
                break

        self.stop()  #stop controller
        self.stop_threads()  
        self.is_stop = True
        _log.debug('%s generating SIGALRM', self.name)
        signal.alarm(1)  #generate signal to wake up the main thread
            
    def stop(self):
        """
        Public method to stop the controller and in turn the agent.
        """
        
        api.session.stop()  #set the global stop event
        helper.ThreadMonitor().register(callback = exit_status.AGENT_ERR_NOT_RESPONDING)  #monitor current thread to prevent agent from hanging
        
    def stop_threads(self):
        """
        Method to stop all non-daemon threads
        """
        
        _log.debug('Stopping all threads')
        rtc.session and rtc.session.stop()  #stop socket-io
        api.session.logout()  #logout from currrent session 
        api.session.close()  #close the session, so that any blocking operation in the session is aborted immediately
        threads = threading.enumerate()
        curr_thread = threading.current_thread()

        #wait for all non-daemon thread to finish
        for thread in threads:
            if thread.ident != curr_thread.ident and thread.ident != self.main_thread.ident and thread.daemon != True:
                _log.debug('Waiting for %s' % unicode(thread))
                thread.join()
                
def set_signal_handler(sig, handler):
    """
    Callback function to handle various signals.
    
    Args:
        sig: signal to handle
        handler: callback function
    """
    
    key = [n for n in dir(signal) if n.startswith('SIG') and not n.startswith('SIG_') and getattr(signal, n) == sig][0]
    
    if handler == signal.SIG_IGN:
        if key in _active_signals:
            del _active_signals[key]
    else:
        _active_signals[key] = 1
        
    signal.signal(sig, handler)

def sig_handler(signum, *args):    
    """
    Callback function to handle various signals.
    """
    
    if signum == signal.SIGTERM:
        _log.info('Received SIGTERM')
        set_signal_handler(signal.SIGTERM, signal.SIG_IGN)  #ignore this event from now on
        Controller().stop()  #ask the controller to stop
    elif signum == signal.SIGINT:
        _log.info('Received SIGINT')
        set_signal_handler(signal.SIGINT, signal.SIG_IGN)  #ignore this event from now on
        Controller().stop()  #ask the controller to stop
    elif signum == signal.SIGALRM:
        _log.debug('Received SIGALRM')
        signal.alarm(0)  #reset SIGALRM
    elif signum == signal.SIGUSR1:
        _log.info('Received SIGUSR1')
        dump_stack_traces()  #dump the stack trace of all the threads in the process
        
def dump_stack_traces():
    """
    Function to dump the stack trace of all the threads to a file
    """
    
    trace = helper.Utils.get_stack_trace()  #get the stack trace of all the threads
    f, timestamp = None, int(time.time() * 1000)
    
    try:
        path = helper.Utils.get_safe_path(universal.Universal().exe_path + ('var/log/stack-trace-%d.log' % timestamp))  #unique filename for stack trace
        f = open(path, 'w')
        f.write(trace)
        _log.info('Stack trace saved at %s' % path)
    except Exception as e:
        _log.error('Failed to save stack trace; %s' % unicode(e))
    finally:
        f and f.close()
        
def run():
    """
    Function that starts the controller module operations
    """
    
    controller = Controller()  #Controller instance
    
    #install signal handlers
    set_signal_handler(signal.SIGALRM, sig_handler)
    set_signal_handler(signal.SIGTERM, sig_handler)
    set_signal_handler(signal.SIGINT, sig_handler)
    set_signal_handler(signal.SIGUSR1, sig_handler)
    
    controller.start()
    
    while 1:  #wait and process the signals
        active_signals = ' or '.join(_active_signals.keys())
        active_signals and _log.debug('Waiting for signals %s' % active_signals)
        signal.pause()
        
        if controller.is_stop == True:  #is controller stopped
            controller.join()
            break
