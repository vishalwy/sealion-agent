#!/usr/bin/python
from src.globals import Globals

try:
    globals = Globals()
except RuntimeError, e:
    print e
    exit()
    
response = globals.connect()
Globals.handle_conn_response(response)




#exit()
#
#
#import pdb
#import threading
#import subprocess
#import time
#import json
#from lib import requests
#
#
#               
#
#session = requests.Session()
#data = {'orgToken': 'def111c8-f6a5-404c-9e57-8bac3bb8b416', 'agentVersion': '2.0.0'}
#is_response_success = False
#response = None
#
#while is_response_success is False:
#    response = session.post(get_complete_url('/52d7f59852a35d8c56000004/sessions'), data=data)
#    is_response_success = is_success(response)
#    
#activities = response.json()['activities']
#ActivityThread.session = session
#SocketIOThread.session = session
#SocketIOThread().start()
#
#for i in range(0, len(activities)):
#    ActivityThread(activities[i]).start()
#
#print 'Exiting Main Thread'

