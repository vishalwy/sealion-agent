import sys
sys.path.append('lib/service') 

from daemon import Daemon

class MyDaemon(Daemon):
    def run(self):
        import __init__

if __name__ == "__main__":
	daemon = MyDaemon('/home/vishal/workspace/sealion/agent/code/var/run/sealion.pid')
	if len(sys.argv) == 2:
		if 'start' == sys.argv[1]:
			daemon.start()
		elif 'stop' == sys.argv[1]:
			daemon.stop()
		elif 'restart' == sys.argv[1]:
			daemon.restart()
		else:
			print "Unknown command"
			sys.exit(2)
		sys.exit(0)
	else:
		print "usage: %s start|stop|restart" % sys.argv[0]
		sys.exit(2)