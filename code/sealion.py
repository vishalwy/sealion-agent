#!/usr/bin/python
import logging
import os
import sys
import time
import traceback
import signal
import pwd
import subprocess
import json

module_path = os.path.abspath(__file__)
exe_path = os.path.dirname(module_path)
exe_path = exe_path if (exe_path[len(exe_path) - 1] == '/') else (exe_path + '/')
sys.path.append(exe_path)
sys.path.append(exe_path + 'src') 

from daemon import Daemon

_log = logging.getLogger(__name__)

class sealion(Daemon):
    user_name = 'vishal'
    
    @property
    def crash_dump_path(self):
        return '%svar/crash/' % exe_path 
    
    def save_dump(self, type, value, tb):
        path = self.crash_dump_path + ('sealion_%d.dmp' % int(round(time.time() * 1000)))
        dir = os.path.dirname(path)
        f = None
        
        try:
            os.path.isdir(dir) or os.makedirs(dir)            
            report = {
                'timestamp': int(round(time.time() * 1000)),
                'stack': ''.join(traceback.format_exception(type, value, tb))
            }
            
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
            
        return report
    
    def send_crash_dumps(self):        
        from globals import Globals
        globals = Globals()
        path = self.crash_dump_path
        globals.api.stop_event.wait(2 * 60)
        _log.debug('Crash dump sender starting up')
        
        for file in os.listdir(path):
            file_name = path + file
            
            if os.path.isfile(file_name):
                status = globals.Status.UNKNOWN
                report = None
                
                while 1:
                    if globals.api.stop_event.is_set():
                        break
                    
                    report = report if report else self.read_dump(file_name)
                    
                    if report != None:
                        status = globals.api.send_crash_report(report)
                        
                    if api.is_not_connected(status) == False:
                        if status != globals.Status.SUCCESS:
                            _log.error('Currupted crash dump %s' % file_name)
                        
                        _log.info('Removing crash dump %s' % file_name)
                        os.remove(file_name)
                        break
                        
                    globals.api.stop_event.wait(30)
                    
            if globals.api.stop_event.is_set():
                break
                
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
            f = open(self.pidfile, 'w');
            f.close()
        except Exception, e:
            print str(e)
            sys.exit(0)
        
        os.chdir(exe_path)
        error = None
        import __init__
        
        try:
            user = pwd.getpwnam(self.user_name)

            if user.pw_uid != os.getuid():
                os.setgid(user.pw_gid)
                os.setuid(user.pw_uid)
        except KeyError:
            error = 'Failed to find user named ' + self.user_name
        except:
            error = 'Failed to change the group or user to ' + self.user_name

        if error:
            _log(error)
            sys.exit(0)
            
    def on_fork(self):
        self.set_procname('%s-monit' % self.__class__.__name__ )
        ret = os.wait()
        is_resurrect = False
        
        if os.WIFEXITED(ret[1]) == False:
            is_resurrect = True
            _log.error('%s got terminated' % self.__class__.__name__)
        elif os.WEXITSTATUS(ret[1]) != 0:
            is_resurrect = True
            
        if is_resurrect:
            if self.is_crash_loop():
                _log.info('Crash loop detected; contact support@sealion.com to troubleshoot')
            else:                        
                _log.info('Resurrecting %s' % self.__class__.__name__)
                subprocess.call([sys.executable, module_path, 'start'])
            
        sys.exit(0)
        
    def is_crash_loop(self):
        t = int(time.time())
        path = self.crash_dump_path
        files = [f for f in os.listdir(path) if os.path.isfile(path + f) and t - os.path.getmtime(path + f) < 120]
        return len(files) >= 5
        
    def exception_hook(self, type, value, tb):
        if type != SystemExit:
            dump_file = self.save_dump(type, value, tb)
            
            if dump_file:
                _log.error('%s crashed. Dump file saved at %s' % (self.__class__.__name__, dump_file))
            else:
                _log.error('%s crashed. Failed to save dump file' % self.__class__.__name__)
            
            os._exit(1)
    
    def run(self):     
        self.set_procname()
        sys.excepthook = self.exception_hook
        
        from constructs import ExceptionThread
        ExceptionThread(target = self.send_crash_dumps).start()        
        
        import __init__
        __init__.start()
            
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
        sys.stdout.write("Unknown command; Usage: %s start|stop|restart|status\n" % sys.argv[0])    
else:
    sys.stdout.write("Usage: %s start|stop|restart|status\n" % sys.argv[0])
    
sys.exit(0)