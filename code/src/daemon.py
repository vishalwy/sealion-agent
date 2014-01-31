import sys
import os
import time
import atexit
import signal

class Daemon(object):
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
    
    def daemonize(self):
        try: 
            pid = os.fork() 
            
            if pid > 0:
                sys.exit(0) 
        except OSError, e: 
            sys.stderr.write('Failed to daemonize: %d (%s)\n' % (e.errno, e.strerror))
    
        os.chdir("/") 
        os.setsid() 
        os.umask(0) 
    
        try: 
            pid = os.fork() 
        except OSError, e: 
            sys.stderr.write('Failed to daemonize: %d (%s)\n' % (e.errno, e.strerror))
            sys.exit(1) 
            
        if pid == 0:
            if self.initialize() == False:
                sys.exit(1)
        else:
            sys.stdout.write('%s started successfully\n' % self.__class__.__name__)
            sys.exit(0)             
            
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        atexit.register(self.delpid)
        pid = str(os.getpid())
        file(self.pidfile, 'w+').write('%s\n' % pid)
    
    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if pid:
            sys.stdout.write('%s is already running\n' % self.__class__.__name__)
            sys.exit(1)            
        
        self.daemonize()
        self.run()

    def stop(self):
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if not pid:
            sys.stdout.write('%s is not running\n' % self.__class__.__name__)
            return

        try:
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
        except OSError, err:
            err = str(err)
            
            if err.find('No such process') > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
                    
                sys.stdout.write('%s stopped successfully\n' % self.__class__.__name__)
            else:
                print sys.stderr.write(err)
                sys.exit(1)

    def restart(self):        
        self.stop()
        self.start()
        
    def status(self):
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if pid:
            sys.stdout.write('%s is running' % self.__class__.__name__)
        elif not pid:
            sys.stdout.write('%s is not running' % self.__class__.__name__)
            
    def initialize(self):
        return True

    def run(self):
        pass
        