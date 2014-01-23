

class ActivityThread(threading.Thread):
    def __init__(self, activity):
        threading.Thread.__init__(self)
        ActivityThread.threadid = ActivityThread.threadid + 1
        self.threadid = ActivityThread.threadid
        self.activity = activity;

    def run(self):
        while 1:
            print 'Executing ' + self.activity['name']
            timestamp = int(round(time.time() * 1000))
            ret = ActivityThread.execute(self.activity['command'])
            print 'Sending ' + self.activity['name']
            data = {'returnCode': ret['returncode'], 'timestamp': timestamp, 'data': ret['output']}
            ActivityThread.session.post(get_complete_url('/1/data/activities/' + self.activity['_id']), data=data)
            time.sleep(self.activity['interval'])            

    @staticmethod
    def execute(command):
        ret = {};
        p = subprocess.Popen(['sh', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.communicate();
        ret['output'] = output[0] if output[0] else output[1]
        ret['returncode'] = p.returncode;
        return ret