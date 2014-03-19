__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__license__ = 'GPL'
__email__ = 'support@sealion.com'

import sys
import os
import time
import atexit
import signal
import os.path

class Daemon(object):
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
    
    def daemonize(self):
        self.initialize()
        
        try: 
            pid = os.fork() 
            
            if pid > 0:
                sys.stdout.write('%s started successfully\n' % self.__class__.__name__)
                sys.exit(0)
        except OSError as e: 
            sys.stderr.write('Failed to daemonize: %d (%s)\n' % (e.errno, e.strerror))
     
        os.chdir("/")
        os.setsid() 
        os.umask(0) 
    
        try: 
            pid = os.fork()  
        except OSError as e: 
            sys.stderr.write('Failed to daemonize: %d (%s)\n' % (e.errno, e.strerror))
            sys.exit(1) 
            
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(self.stdin, 'r')
        so = open(self.stdout, 'a+')
        se = open(self.stderr, 'a+')
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        
        if pid > 0:
            self.on_fork(pid)
            sys.exit(0)
        
        atexit.register(self.delete_pid)
        pid = str(os.getpid())
        
        with open(self.pidfile, 'w+') as f:
            f.write('%s\n' % pid)
    
    def delete_pid(self):
        try:
            os.remove(self.pidfile)
        except:
            pass

    def start(self):
        if self.status(True):
            sys.stdout.write('%s is already running\n' % self.__class__.__name__)
            sys.exit(1)            
        
        self.daemonize()
        self.run()

    def stop(self):
        if self.status(True) == False:
            sys.stdout.write('%s is not running\n' % self.__class__.__name__)
            return
        
        pid = self.get_pid()

        try:
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
        except OSError as err:
            err = str(err)
            
            if err.find('No such process') > 0:
                if os.path.exists(self.pidfile):
                    try:
                        os.remove(self.pidfile)
                    except Exception as e:
                        sys.stderr.write(str(e) + '\n')
                        sys.exit(1)
                    
                sys.stdout.write('%s stopped successfully\n' % self.__class__.__name__)
            else:
                sys.stderr.write(err + '\n')
                sys.exit(1)

    def restart(self):        
        self.stop()
        self.start()
        
    def status(self, query = False):
        ret = True
        pid = self.get_pid()
    
        if pid and os.path.exists('/proc/%d' % pid):
            query == False and sys.stdout.write('%s is running\n' % self.__class__.__name__)
        else:
            query == False and sys.stdout.write('%s is not running\n' % self.__class__.__name__)
            ret = False
            
        return ret
    
    def get_pid(self):
        f = None
        
        try:
            f = open(self.pidfile, 'r')
            pid = int(f.read().strip())
        except:
            pid = None
        finally:
            f and f.close()

        return pid
            
    def initialize(self):
        return True
    
    def on_fork(self, cpid):
        pass

    def run(self):
        pass
        