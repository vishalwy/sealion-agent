import logging
import os
import sys
import time
import traceback
import signal
import pwd
import subprocess
import json

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.append(exe_path)
sys.path.append(exe_path + 'src') 

from daemon import Daemon

_log = logging.getLogger(__name__)

class sealion(Daemon):
    user_name = 'sealion'
    monit_interval = 60
    crash_dump_threshold = 5
    
    @property
    def crash_dump_path(self):
        return '%svar/crash/' % exe_path 
    
    def save_dump(self, type, value, tb):
        from globals import Globals
        globals = Globals()
        path = self.crash_dump_path + ('sealion_%d.dmp' % int(time.time() * 1000))
        dir = os.path.dirname(path)
        f = None
        
        try:
            os.path.isdir(dir) or os.makedirs(dir)            
            report = {
                'timestamp': int(time.time() * 1000),
                'stack': ''.join(traceback.format_exception(type, value, tb))
            }
            
            if hasattr(globals.config.agent, 'orgToken'):
                report['orgToken'] = globals.config.agent.orgToken
                
            if hasattr(globals.config.agent, '_id'):
                report['_id'] = globals.config.agent._id
            
            f = open(path, 'w')
            json.dump(report, f)
        except:
            return None
        finally:
            f and f.close()
        
        return path
    
    def read_dump(self, file_name):
        f, report = None, None
        
        try:
            f = open(file_name, 'r')
            report = json.load(f)
        except:
            pass
        finally:
            f and f.close()
            
        if report and (not report.get('orgToken') or not report.get('_id')):
            report = None
        
        return report
    
    def send_crash_dumps(self):        
        _log.debug('Crash dump sender starting up')        
        crash_dump_timeout = (self.monit_interval * self.crash_dump_threshold) + 10
        from globals import Globals
        globals = Globals()
        path = self.crash_dump_path
        _log.debug('Crash dump sender waiting for stop event for %d seconds', crash_dump_timeout)
        globals.api.stop_event.wait(crash_dump_timeout)
        
        try:
            for file in os.listdir(path):
                file_name = path + file

                if os.path.isfile(file_name):
                    status = globals.APIStatus.UNKNOWN
                    report = None

                    while 1:
                        if globals.api.stop_event.is_set():
                            break

                        report = report if report else self.read_dump(file_name)

                        if report == None:
                            break

                        status = globals.api.send_crash_report(report)

                        if api.is_not_connected(status) == False:                        
                            _log.info('Removing crash dump %s' % file_name)
                            os.remove(file_name)
                            break

                        globals.api.stop_event.wait(30)

                if globals.api.stop_event.is_set():
                    break
        except:
            pass
                
        _log.debug('Crash dump sender shutting down')
    
    def set_procname(self, proc_name = None):
        proc_name = proc_name if proc_name else self.__class__.__name__
        
        try:
            from ctypes import cdll, byref, create_string_buffer
            libc = cdll.LoadLibrary('libc.so.6')
            buff = create_string_buffer(len(proc_name) + 1)
            buff.value = proc_name
            libc.prctl(15, byref(buff), 0, 0, 0)
        except:
            pass
        
    def initialize(self):        
        try:
            user = pwd.getpwnam(self.user_name)

            if user.pw_uid != os.getuid():
                os.setgid(user.pw_gid)
                os.setuid(user.pw_uid)
        except KeyError as e:
            _log.error('Failed to find user named %s; %s' % (self.user_name, str(e)))
            sys.exit(0)
        except Exception as e:
            _log.error('Failed to change the group or user to %s; %s' % (self.user_name, str(e)))
            sys.exit(0)
            
        try:
            dir = os.path.dirname(self.pidfile)
            
            if os.path.isdir(dir) != True:
                os.makedirs(dir)
            
            f = open(self.pidfile, 'w');
            f.close()
        except Exception as e:
            _log.error(str(e))
            sys.exit(1)
        
        os.chdir(exe_path)
        import main
            
    def on_fork(self, cpid):        
        try:
            subprocess.Popen([exe_path + 'bin/monit.sh', str(cpid), str(self.monit_interval)])
        except:
            _log.error('Failed to open monitoring script')
            
        sys.exit(0)
        
    def is_crash_loop(self):
        t = int(time.time())
        path = self.crash_dump_path
        crash_dump_timeout = self.monit_interval * self.crash_dump_threshold
        
        try:
            files = [f for f in os.listdir(path) if os.path.isfile(path + f) and t - os.path.getmtime(path + f) < crash_dump_timeout]
        except:
            return 0
        
        return len(files) >= 4
        
    def exception_hook(self, type, value, tb):
        if type != SystemExit:
            dump_file = self.save_dump(type, value, tb)
            
            if dump_file:
                _log.error('%s crashed. Dump file saved at %s' % (self.__class__.__name__, dump_file))
            else:
                _log.error('%s crashed. Failed to save dump file' % self.__class__.__name__)
            
            os._exit(1)
    
    def run(self):     
        self.set_procname('%s' % self.__class__.__name__ )
        sys.excepthook = self.exception_hook
        is_update_only_mode = False
        
        if self.is_crash_loop() == True:
            _log.info('Crash loop detected; starting agent in update only mode')
            is_update_only_mode = True
        
        from constructs import ThreadEx
        ThreadEx(target = self.send_crash_dumps).start()
        import main
        main.start(is_update_only_mode)
            
def sig_handler(signum, frame):    
    if signum == signal.SIGINT:
        exit(2)
    
signal.signal(signal.SIGINT, sig_handler)
daemon = sealion(exe_path + 'var/run/sealion.pid')

if len(sys.argv) == 2:
    if sys.argv[1] == 'start':
        daemon.start()
    elif sys.argv[1] == 'stop':
        daemon.stop()
    elif sys.argv[1] == 'restart':
        daemon.restart()
    elif sys.argv[1] == 'status':
        daemon.status()
    else:
        sys.stdout.write("Unknown command; Usage: %s start|stop|restart|status\n" % daemon.__class__.__name__)    
else:
    sys.stdout.write("Usage: %s start|stop|restart|status\n" % daemon.__class__.__name__)
    
sys.exit(0)