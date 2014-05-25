__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import tempfile
import subprocess
import logging
import threading
import subprocess
import signal
import sys
import time
import api
import rtc
import storage
import globals
import connection
import services
import exit_status
import helper
from constructs import *

_log = logging.getLogger(__name__)

class Controller(SingletonType('ControllerMetaClass', (ThreadEx, ), {})):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = globals.Globals()
        self.is_stop = False
        self.main_thread = threading.current_thread()
        self.activities = {}
        self.updater = None
    
    def handle_response(self, status):
        _log.debug('Handling response status %d.' % status)
        
        if status == api.Status.SUCCESS:
            return True
        elif api.API.is_not_connected(status):
            _log.info('Failed to establish connection.')
        elif status == api.Status.NOT_FOUND:           
            try:
                _log.info('Uninstalling agent.')
                subprocess.Popen([self.globals.exe_path + 'uninstall.sh'])
            except:
                _log.error('Failed to open uninstall script.')
                
        elif status == api.Status.UNAUTHORIZED:
            _log.error('Agent unauthorized to connect')
        elif status == api.Status.BAD_REQUEST:
            _log.error('Server marked the request as bad')
        elif status == api.Status.SESSION_CONFLICT:
            _log.error('Agent session conflict')

        return False
    
    @staticmethod
    def is_rtc_heartbeating():
        if api.session.is_authenticated == False:
            return True
        
        if rtc.session == None:
            return True
        else:
            ret = rtc.session.is_heartbeating()
            ret == False and rtc.session.update_heartbeat()
            return ret
        
    def update_agent(self, event = None):
        if self.updater != None:
            return
        
        self.updater = True
        version_details = api.unauth_session.get_agent_version()
        
        if type(version_details) is dict and version_details['agentVersion'] != self.globals.config.agent.agentVersion:
            self.updater = ThreadEx(target = self.agent_updater_proc, name = 'Updater', args = (version_details,))
            self.updater.daemon = True
            self.updater.start()
        else:
            self.updater = None
            
    def agent_updater_proc(self, version_details):
        temp_dir = helper.Utils.get_safe_path(self.globals.exe_path + 'tmp/')
        temp_dir = tempfile.mkdtemp(dir = temp_dir)
        temp_dir = temp_dir[:-1] if temp_dir[len(temp_dir) - 1] == '/' else temp_dir
        self.download_update(version_details, temp_dir) and self.install_update(version_details, temp_dir)
        subprocess.call(['bash', '-c', 'rm -rf "%s"' % temp_dir])
        self.updater = None
        
    def download_update(self, version_details, temp_dir):
        download_url = version_details['agentDownloadURL']
        filename = '%s/%s' % (temp_dir, download_url.split('/')[-1])
        _log.info('Update found; Downloading update version %s to %s' % (version_details['agentVersion'], filename))
        f = open(filename, 'wb')
        response = api.unauth_session.exec_method('get', {'retry_count': 0}, download_url, stream = True)
        
        if api.API.is_success(response) == False:
            api.unauth_session.error('Failed to download the update', response, True)
            f and f.close()
            return False
            
        is_completed = False
        
        try:
            for chunk in response.iter_content(chunk_size = 1024):
                if self.globals.stop_event.is_set():
                    _log.info('%s received stop event' % self.name)
                    break

                if chunk:
                    f.write(chunk)
                    f.flush()

            is_completed = True
        except Exception as e:
            _log.error(str(e))
        finally:
            f.close()
            
        if is_completed == True:
            _log.info('Update version %s is succesfully downloaded to %s' % (version_details['agentVersion'], filename))
        else:
            _log.info('Aborted downloading update %s', version_details['agentVersion'])
            return False
               
        if subprocess.call(['tar', '-xf', "%s" % filename, '--directory=%s' % temp_dir]):
            _log.error('Failed to extract update from  %s' % filename)
            return False
        
        _log.debug('Extracted update from %s to %s' % (filename, temp_dir))
        return True
            
    def install_update(self, version_details, temp_dir):
        _log.info('Installing update version %s', version_details['agentVersion'])
        format_spec = {
            'temp_dir': temp_dir, 
            'exe_path': self.globals.exe_path, 
            'executable': sys.executable, 
            'org_token': self.globals.config.agent.orgToken, 
            'agent_id': self.globals.config.agent._id
        }
        format = '"%(temp_dir)s/sealion-agent/install.sh" -a %(agent_id)s -o %(org_token)s -i "%(exe_path)s" -p "%(executable)s" && rm -rf "%(temp_dir)s"'
        subprocess.call(['bash', '-c', format % format_spec], preexec_fn = os.setpgrp)
        time.sleep(5)
        _log.error('Failed to install update version %s' % version_details['agentVersion'])
        
    def exe(self):        
        while 1:
            if self.globals.is_update_only_mode == True:
                self.update_agent()
                _log.debug('%s waiting for stop event for %d seconds.' % (self.name, 5 * 60, ))
                self.globals.stop_event.wait(5 * 60)

                if self.globals.stop_event.is_set():
                    _log.debug('%s received stop event.', self.name)
                    self.globals.set_time_metric('stopping_time')
                    break
            else:
                self.globals.event_dispatcher.bind('update_agent', self.update_agent)
                
                if self.handle_response(connection.Connection().connect()) == False:
                    self.globals.set_time_metric('stopping_time')
                    break
                    
                store = storage.Storage()
                job_producer = services.JobProducer(store)

                if store.start() == False:
                    self.globals.set_time_metric('stopping_time')
                    break
                    
                job_producer.start()

                while 1:              
                    if Controller.is_rtc_heartbeating() == False:
                        api.session.get_config()
                    
                    finished_job_count = 0

                    for job in job_producer.finish_jobs():
                        job.post_output()
                        finished_job_count += 1

                    finished_job_count and _log.debug('Finished execution of %d activities.' % finished_job_count)
                    self.globals.stop_event.wait(5)

                    if self.globals.stop_event.is_set():
                        _log.debug('%s received stop event.', self.name)
                        self.globals.set_time_metric('stopping_time')
                        job_producer.finish_jobs(None)
                        break
                        
                self.handle_response(api.session.stop_status)
                break

        self.stop_threads()
        self.is_stop = True

        _log.debug('%s generating SIGALRM', self.name)
        signal.alarm(1)
            
    def stop(self):
        api.session.stop()
        self.is_stop = True
        helper.ThreadMonitor().register(callback = exit_status.AGENT_ERR_NOT_RESPONDING)
        
    def stop_threads(self):
        _log.debug('Stopping all threads.')
        api.session.stop()
        rtc.session and rtc.session.stop()
        api.session.logout()
        api.session.close()
        threads = threading.enumerate()
        curr_thread = threading.current_thread()

        for thread in threads:
            if thread.ident != curr_thread.ident and thread.ident != self.main_thread.ident and thread.daemon != True:
                _log.debug('Waiting for %s.' % str(thread))
                thread.join()

def sig_handler(signum, frame):    
    if signum == signal.SIGTERM:
        _log.info('Received SIGTERM')
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        Controller().stop()
    elif signum == signal.SIGINT:
        _log.info('Received SIGINT')
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        Controller().stop()
    elif signum == signal.SIGALRM:
        _log.debug('Received SIGALRM')
        signal.alarm(0)
    elif signum == signal.SIGUSR1:
        _log.debug('Received SIGUSR1')
        dump_stack_traces()
        
def dump_stack_traces():
    trace = helper.Utils.get_stack_trace()
    f, timestamp = None, int(time.time() * 1000)
    
    try:
        path = helper.Utils.get_safe_path(globals.Globals().exe_path + ('var/log/stack-trace-%d.log' % timestamp))
        f = open(path, 'w')
        f.write(trace)
        _log.info('Stack trace saved at %s' % path)
    except Exception as e:
        _log.error('Failed to save stack trace; %s' % str(e))
    finally:
        f and f.close()
        
def stop(status = 0):
    _log.info('Agent shutting down with status code %d.' % status)
    _log.debug('Took %f seconds to shutdown.' % (globals.Globals().get_stoppage_time()))
    _log.info('Ran for %s hours.' %  globals.Globals().get_run_time_str())
    sys.exit(status)
    
def start():
    _log.info('Agent starting up.')
    _log.info('Using python binary at %s.' % sys.executable)
    _log.info('Python version : %s.' % globals.Globals().details['pythonVersion'])
    _log.info('Agent version  : %s.' % globals.Globals().config.agent.agentVersion)
    controller = Controller()
    signal.signal(signal.SIGALRM, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGUSR1, sig_handler)
    controller.start()
    
    while 1:
        _log.debug('Waiting for signals SIGALRM or SIGTERM or SIGINT or SIGUSR1')
        signal.pause()
        
        if controller.is_stop == True:
            controller.join()
            break

    stop()
