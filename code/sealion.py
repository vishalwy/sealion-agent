import os
import sys
import time

exe_path = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
exe_path = exe_path if (exe_path[len(exe_path) - 1] == '/') else (exe_path + '/')
sys.path.append(exe_path)
sys.path.append(exe_path + 'lib/service') 

from daemon import Daemon

class Sealion(Daemon):
    def save_dump(self, exception):
        path = '%svar/crash/agent%d.dmp' % (exe_path, int(time.time()))
        dir = os.path.dirname(path)
        os.path.isdir(dir) or os.makedirs(dir)
        f = open(path, 'w')
        f.write(str(exception) + ' ' + exe_path)
        f.close()
    
    def run(self):
        os.chdir(exe_path)
        
        try:        
            import __init__
        except Exception, e:
            self.save_dump(e)

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