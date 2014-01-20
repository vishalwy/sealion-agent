#!/usr/bin/python

import threading
import subprocess
import time
import json
from lib import requests
from lib.socketio_client import SocketIO, BaseNamespace

def is_success(response):
    return True if (response.status_code == 304 or (response.status_code >= 200 and response.status_code < 300)) else False

def get_complete_url(url, is_socket_io = False):
    base_url = 'https://api-rituparna.sealion.com' + ('' if is_socket_io else '/agents')
    base_url = base_url if url[0] == '/' else (base_url + '/')
    base_url = base_url + ('' if is_socket_io else url)
    return base_url

class ActivityThread(threading.Thread):
    threadid = 0
    session = None

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

class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        print '[Connected]'

    def on_activity_updated(self, *args):
        print '[activity_updated]'

    def on_activitylist_in_category_updated(self, *args):
        print '[activitylist_in_category_updated]'

    def on_agent_removed(self, *args):
        print '[agent_removed]'

    def on_org_token_resetted(self, *args):
        print '[org_token_resetted]'

    def on_server_category_changed(self, *args):
        print '[server_category_changed]'

    def on_activity_deleted(self, *args):
        print '[activity_deleted]'

class SocketIOThread(threading.Thread):
    session = None

    def run(self):
        socket_io = SocketIO(get_complete_url('/', True), 443, SocketIONamespace, cookies=session.cookies, proxies=session.proxies)
        socket_io.wait()               

session = requests.Session()
data = {'orgToken': 'def111c8-f6a5-404c-9e57-8bac3bb8b416', 'agentVersion': '2.0.0'}
is_response_success = False
response = None

while is_response_success is False:
    response = session.post(get_complete_url('/52d7f59852a35d8c56000004/sessions'), data=data)
    is_response_success = is_success(response)
    
activities = response.json()['activities']
ActivityThread.session = session
SocketIOThread.session = session
SocketIOThread().start()

for i in range(0, len(activities)):
    ActivityThread(activities[i]).start()

print 'Exiting Main Thread'

