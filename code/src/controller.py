import logging
import threading
import time
import subprocess
import signal
import sys
import api
import storage
import globals
import connection
import services
from datetime import datetime
from constructs import *

_log = logging.getLogger(__name__)
_metric = {'starting_time': 0, 'stopping_time': 0}

class Controller(SingletonType('ControllerMetaClass', (ThreadEx, ), {})):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.globals = globals.Globals()
        self.api = api.API()
        self.is_stop = False
        self.main_thread = threading.current_thread()
        self.activities = {}
        self.activities_lock = threading.RLock()
    
    def handle_response(self, status):
        _log.debug('Handling response status %d.' % status)
        
        if status == self.api.status.SUCCESS:
            return True
        elif self.api.is_not_connected(status):
            _log.info('Failed to establish connection.')
        elif status == self.api.status.NOT_FOUND:           
            try:
                _log.info('Uninstalling agent.')
                subprocess.Popen([self.globals.exe_path + 'uninstall.sh'])
            except:
                _log.error('Failed to open uninstall script.')
                
        elif status == self.api.status.UNAUTHORIZED:
            _log.error('Agent unauthorized to connect')
        elif status == self.api.status.BAD_REQUEST:
            _log.error('Server marked the request as bad')
        elif status == self.api.status.SESSION_CONFLICT:
            _log.error('Agent session conflict')

        return False
        
    def exe(self):        
        while 1:
            if self.globals.is_update_only_mode == True:
                version = self.api.get_agent_version()
                version_type = type(version)

                if (version_type is str or version_type is unicode) and version != self.globals.config.agent.agentVersion:
                    self.api.update_agent()

                _log.debug('%s waiting for stop event for %d seconds.' % (self.name, 5 * 60, ))
                self.globals.stop_event.wait(5 * 60)

                if self.globals.stop_event.is_set():
                    _log.debug('%s received stop event.', self.name)
                    break
            else:
                if self.handle_response(connection.Connection().connect()) == False:
                    break
                    
                store = storage.Storage()

                if store.start() == False:
                    break
                    
                job_producer = services.JobProducer(store)
                job_producer.start()

                while 1:             
                    finished_job_count = 0

                    for job in job_producer.finish_jobs():
                        job.post_output()
                        finished_job_count += 1

                    finished_job_count and _log.info('Finished execution of %d activities.' % finished_job_count)
                    self.globals.stop_event.wait(5)

                    if self.globals.stop_event.is_set():
                        _log.debug('%s received stop event.', self.name)
                        _metric['stopping_time'] = time.time()
                        job_producer.finish_jobs(None)
                        break
                        
                self.handle_response(self.api.stop_status)
                break

        _metric['stopping_time'] = _metric['stopping_time'] if _metric['stopping_time'] else time.time()
        self.is_stop = True
        self.stop_threads()

        _log.debug('%s generating SIGALRM', self.name)
        signal.alarm(1)
            
    def stop(self):
        self.is_stop = True
        self.api.stop()
        
    def stop_threads(self):
        _log.debug('Stopping all threads.')
        self.api.stop()
        connection.Connection.stop_rtc()
        self.api.logout()
        self.api.close()
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
        
def stop(status = 0):
    _log.info('Agent shutting down with status code %d.' % status)
    _log.debug('Took %f seconds to shutdown.' % (time.time() - _metric['stopping_time']))
    _log.info('Ran for %s hours.' % str(datetime.now() - datetime.fromtimestamp(_metric['starting_time'])))
    exit(status)
    
def start():
    _metric['starting_time'] = time.time()
    _log.info('Agent starting up.')
    _log.info('Using python binary at %s.' % sys.executable)
    _log.info('Python version : %s.' % '.'.join([str(i) for i in sys.version_info]))
    _log.info('Agent version  : %s.' % globals.Globals().config.agent.agentVersion)
    controller = Controller()
    signal.signal(signal.SIGALRM, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    controller.start()
    
    while 1:
        _log.debug('Waiting for signals SIGALRM or SIGTERM or SIGINT')
        signal.pause()
        
        if controller.is_stop == True:
            controller.join()
            break

    stop()
