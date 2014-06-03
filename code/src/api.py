__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import requests
import time
import json
import connection
import globals
from constructs import *

_log = logging.getLogger(__name__)
session = None
unauth_session = None

class Status(Namespace):
    SUCCESS = 0
    NOT_CONNECTED = 1
    NO_SERVICE = 2
    DATA_CONFLICT = 3
    MISMATCH = 4
    BAD_REQUEST = 5
    NOT_FOUND = 6
    UNAUTHORIZED = 7
    SESSION_CONFLICT = 8
    UNKNOWN = -1

class API(requests.Session):    
    def __init__(self, *args, **kwargs):
        requests.Session.__init__(self, *args, **kwargs)
        self.globals = globals.Globals()
        self.stop_status = Status.SUCCESS
        self.is_authenticated = False
        self.is_conn_err = False
            
    @staticmethod
    def is_success(response):
        status_code = response.status_code if response else 500
        return True if (status_code == 304 or (status_code >= 200 and status_code < 300)) else False
    
    @staticmethod
    def print_error(message, response):
        temp = 'Network issue'
        
        if response != None:
            try:
                response_json = response.json()
                code = response_json['code']
                temp = 'Error ' + unicode(code) + '; ' + response_json['message']
            except:
                temp = 'Error ' + unicode(response.status_code)
        
        temp = (message + '; ' + temp) if len(message) else temp
        _log.error(temp)
    
    def set_events(self, stop_event = None, post_event = None):
        if stop_event == True and self.globals.stop_event.is_set() == False:
            _log.debug('Setting stop event')
            self.globals.stop_event.set()
        elif stop_event == False and self.globals.stop_event.is_set() == True:
            _log.debug('Resetting stop event')
            self.globals.stop_event.clear()
        
        if post_event == True and self.globals.post_event.is_set() == False:
            _log.debug('Setting post event')
            self.globals.post_event.set()
        elif post_event == False and self.globals.post_event.is_set() == True and self.globals.stop_event.is_set() == False:
            _log.debug('Resetting post event')
            self.globals.post_event.clear()
    
    def exec_method(self, method, options = {}, *args, **kwargs):
        method = getattr(self, method)
        retry_count = options.get('retry_count', -1)
        retry_interval = options.get('retry_interval', 5)
        is_ignore_stop_event = options.get('is_ignore_stop_event', False)
        is_return_exception = options.get('is_return_exception', False)
        response, i, exception = None, 0, None
        
        if type(kwargs.get('data')) is dict and kwargs.get('headers') == None:
            kwargs['headers'] = {'Content-type': 'application/json', 'Accept': 'text/plain'}
            kwargs['data'] = json.dumps(kwargs['data'])
        
        while retry_count == -1 or i <= retry_count:                
            if i > 0:
                self.globals.stop_event.wait(retry_interval)
                
            if is_ignore_stop_event == False and self.globals.stop_event.is_set():
                break
            
            try:
                response = method(timeout = 10, *args, **kwargs)
            except Exception as e:
                _log.error(unicode(e))
                exception = e
                
            if response != None and response.status_code < 500:
                self.is_conn_err == True and _log.info('Network connection established')
                self.is_conn_err = False
                break
                
            i += 0 if (retry_count == -1 and i > 0) else 1
            
        if response == None and self.is_authenticated == True:
            self.is_conn_err = True
        
        return response if is_return_exception == False else (response, exception)
    
    def ping(self, is_ping_server = False):
        response = None
        
        if is_ping_server == False:
            self.set_events(post_event = True)
        else:
            response = self.exec_method('get', {'retry_count': 0, 'is_return_exception': True}, self.globals.get_url())
            
            if response[0] != None and response[0].status_code < 500:
                _log.debug('Ping server successful')
                self.is_authenticated and self.set_events(post_event = True)
            else:
                API.print_error('Failed to ping server', response[0])
            
        return response
    
    def register(self, **kwargs):
        data = self.globals.config.agent.get_dict(['orgToken', 'name', 'category', 'agentVersion', ('ref', 'tarball')])
        response = self.exec_method('post', kwargs, self.globals.get_url('agents'), data = data)    
        ret = Status.SUCCESS
        
        if API.is_success(response):
            _log.info('Registration successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
        else:
            ret = self.error('Failed to register agent', response)
        
        return ret
    
    def unregister(self):
        ret = Status.SUCCESS
        
        if hasattr(self.globals.config.agent, '_id') == False:
            return ret
        
        response = self.exec_method('delete', {'retry_count': 2}, self.globals.get_url('orgs/%s/servers/%s' % (self.globals.config.agent.orgToken, self.globals.config.agent._id)))
        
        if API.is_success(response) == False:
            ret = self.error('Failed to unregister agent', response)
            
        return ret
    
    def authenticate(self, **kwargs):
        data = self.globals.config.agent.get_dict(['orgToken', 'agentVersion'])
        data['timestamp'] = int(time.time() * 1000)
        data['platform'] = self.globals.details
        response = self.exec_method('post', kwargs, self.globals.get_url('agents/' + self.globals.config.agent._id + '/sessions'), data = data)    
        ret = Status.SUCCESS
        
        if API.is_success(response):
            _log.info('Authentication successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
            self.is_authenticated = True
            self.set_events(post_event = True)
        else:
            ret = self.error('Authentication failed. ', response)
        
        return ret
            
    def get_config(self):
        response = self.exec_method('get', {'retry_count': 0}, self.globals.get_url('agents/1'))
        ret = Status.SUCCESS
        
        if API.is_success(response):
            _log.info('Config updation successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
            self.set_events(post_event = True)
        else:
            ret = self.error('Config updation failed. ', response)
            
        return ret
            
    def post_data(self, activity_id, data):
        response = self.exec_method('post', {'retry_count': 0}, self.globals.get_url('agents/1/data/activities/' + activity_id), data = data)
        ret = Status.SUCCESS
        
        if API.is_success(response):
            _log.debug('Sent activity (%s @ %d)' % (activity_id, data['timestamp']))
            self.set_events(post_event = True)
        else:
            ret = self.error('Failed to send activity (%s @ %d)' % (activity_id, data['timestamp']), response)
            
        return ret
    
    def logout(self):
        ret = Status.SUCCESS
        
        if hasattr(self.globals.config.agent, '_id') == False or self.is_authenticated == False:
            return ret
        
        response = self.exec_method('delete', {'retry_count': 0, 'is_ignore_stop_event': True}, self.globals.get_url('agents/1/sessions/1'))
        
        if API.is_success(response):
            _log.info('Logout successful')
        else:
            ret = self.error('Logout failed. ', response, True)

        return ret
    
    def get_agent_version(self):
        data = self.globals.config.agent.get_dict([('orgToken', ''), ('_id', ''), ('agentVersion', '')])
        url = self.globals.get_url('orgs/%s/agents/%s/agentVersion' % (data['orgToken'], data['_id']))
        response = self.exec_method('get', {'retry_count': 0}, url, params = {'agentVersion': data['agentVersion']})
        
        if API.is_success(response):
            ret = response.json()
            _log.debug('Available agent version %s' % ret['agentVersion'])
        else:
            ret = self.error('Failed to get agent version ', response, True)
            ret == Status.MISMATCH and self.stop()
        
        return ret
    
    def send_crash_report(self, data, **kwargs):
        temp = data.copy()
        data = temp
        orgToken, agentId = data['orgToken'], data['_id']
        del data['orgToken'], data['_id']
        response = self.exec_method('post', {'retry_count': 0}, self.globals.get_url('orgs/%s/agents/%s/crashreport' % (orgToken, agentId)), data = data)
        ret = Status.SUCCESS
        
        if API.is_success(response):
            _log.info('Sent dump @ %d' % data['timestamp'])
        else:
            ret = self.error('Failed to send dump ', response, True)
        
        return ret
    
    def stop(self, stop_status = None):
        self.set_events(True, True)
        
        if stop_status != None:
            self.stop_status = stop_status
    
    def error(self, message, response, is_ignore_status = False):        
        API.print_error(message, response)    
        
        if response == None:
            is_ignore_status == False and self.globals.stop_event.is_set() == False and self.set_events(post_event = False)
            return Status.NOT_CONNECTED
        
        status, ret, post_event, exec_func, args = response.status_code, Status.UNKNOWN, True, None, ()
        
        try:
            code = response.json()['code']
        except:
            code = 0
            
        if status >= 500:
            post_event = False
            ret = Status.NO_SERVICE
        elif status == 400:
            ret = Status.BAD_REQUEST
        elif status == 401:
            if code == 200004:
                ret = Status.MISMATCH
            else:
                if code == 200001 and self.stop_status == Status.SUCCESS:
                    post_event = False
                    exec_func = connection.Connection().reconnect
                else:
                    post_event = None
                    exec_func = self.stop
                    
                ret = Status.UNAUTHORIZED
        elif status == 404:
            post_event = None
            exec_func = self.stop
            args = (Status.NOT_FOUND,)
            ret = Status.NOT_FOUND
        elif status == 409:
            if code == 204011:
                ret = Status.DATA_CONFLICT
            elif code == 204012:
                post_event = None
                exec_func = self.stop
                args = (Status.SESSION_CONFLICT,)
                ret = Status.SESSION_CONFLICT
                
        if is_ignore_status == False:
            self.set_events(post_event = post_event)
            exec_func and exec_func(*args)
            
        return ret
    
def is_not_connected(status):
    if status == Status.NOT_CONNECTED or status == Status.NO_SERVICE or status == Status.UNKNOWN:
        return True

    return False
    
def create_session():
    global session
    session = API()
    return session

def create_unauth_session():
    global unauth_session
    unauth_session = API()
    return unauth_session
