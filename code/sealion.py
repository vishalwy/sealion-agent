#!/usr/bin/python

import os
import sys
import time
import traceback
import signal

exe_path = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
exe_path = exe_path if (exe_path[len(exe_path) - 1] == '/') else (exe_path + '/')
sys.path.append(exe_path)
sys.path.append(exe_path + 'lib/service') 

from daemon import Daemon

class Sealion(Daemon):
    def save_dump(self):
        path = '%svar/crash/agent%d.dmp' % (exe_path, int(time.time()))
        dir = os.path.dirname(path)
        os.path.isdir(dir) or os.makedirs(dir)
        f = open(path, 'w')
        traceback.print_exc(file = f)
        f.close()
    
    def run(self):
        os.chdir(exe_path)
        
        try:        
            import __init__
            __init__.start()
        except:
            self.save_dump()
            
def sig_handler(signum, frame):    
    if signum == signal.SIGINT:
        exit(2)
    
signal.signal(signal.SIGINT, sig_handler)

daemon = Sealion(exe_path + 'var/run/sealion.pid')

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
        sys.stdout.write("Unknown command\n")
        sys.exit(2)
    sys.exit(0)
else:
    sys.stdout.write("Usage: %s start|stop|restart|status\n" % sys.argv[0])
    sys.exit(2)