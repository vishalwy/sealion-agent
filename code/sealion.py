#!/usr/bin/python
import logging
import os
import sys
import time
import traceback
import signal
import pwd
import subprocess

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
        path = self.crash_dump_path + ('agent%d.dmp' % int(time.time()))
        dir = os.path.dirname(path)
        
        try:
            os.path.isdir(dir) or os.makedirs(dir)
            f = open(path, 'w')
            traceback.print_exception(type, value, tb, file = f)
            f.close()
        except:
            return None
        
        return path
    
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
            _log.info('Resurrecting %s' % self.__class__.__name__)
            subprocess.call([sys.executable, module_path, 'start'])
            pass
            
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
        import __init__
        
        if self.is_crash_loop():
            _log.info('Detected crash loop; starting agent in update only mode')
            
            while 1:
                time.sleep(5)
        
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