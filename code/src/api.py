__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import logging
import requests
import subprocess
import time
import json
import re
import connection
import globals
from constructs import *

_log = logging.getLogger(__name__)

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

class API(SingletonType('APIMetaClass', (requests.Session, ), {})):    
    status = Status
    
    def __init__(self, *args, **kwargs):
        requests.Session.__init__(self, *args, **kwargs)
        self.globals = globals.Globals()
        self.stop_status = self.status.SUCCESS
        self.is_authenticated = False
        self.updater = None
        self.is_conn_err = False
        self.globals.event_dispatcher.bind('update_agent', self.update_agent)
            
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
                temp = 'Error ' + str(code) + '; ' + response_json['message']
            except:
                temp = 'Error ' + str(response.status_code)
        
        temp = (message + '; ' + temp) if len(message) else temp
        _log.error(temp)
    
    def is_not_connected(self, status):
        if status == self.status.NOT_CONNECTED or status == self.status.NO_SERVICE:
            return True
        
        return False
    
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
    
    def get_url(self, path = ''):
        path.strip()
        
        if len(path):
            path = path if path[0] == '/' else ('/' + path)
                  
        return self.globals.config.agent.apiUrl + path
    
    def exec_method(self, method, options = {}, *args, **kwargs):
        method = getattr(self, method)
        retry_count = options.get('retry_count', -1)
        retry_interval = options.get('retry_interval', 5)
        is_ignore_stop_event = options.get('is_ignore_stop_event', False)
        is_return_exception = options.get('is_return_exception', False)
        response, i, exception = None, 0, None
        
        while retry_count == -1 or i <= retry_count:                
            if i > 0:
                self.globals.stop_event.wait(retry_interval)
                
            if is_ignore_stop_event == False and self.globals.stop_event.is_set():
                break
            
            try:
                response = method(timeout = 10, *args, **kwargs)
            except Exception as e:
                _log.error(str(e))
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
            response = self.exec_method('get', {'retry_count': 0, 'is_return_exception': True}, self.get_url())
            
            if response[0] != None and response[0].status_code < 500:
                _log.debug('Ping server successful')
                self.is_authenticated and self.set_events(post_event = True)
            else:
                API.print_error('Failed to ping server', response[0])
            
        return response
    
    def register(self, **kwargs):
        data = self.globals.config.agent.get_dict(['orgToken', 'name', 'category', 'agentVersion', ('ref', 'tarball')])
        response = self.exec_method('post', kwargs, self.get_url('agents'), data = data)    
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.info('Registration successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
        else:
            ret = self.error('Failed to register agent', response)
        
        return ret
    
    def unregister(self):
        ret = self.status.SUCCESS
        
        if hasattr(self.globals.config.agent, '_id') == False:
            return ret
        
        response = self.exec_method('delete', {'retry_count': 2}, self.get_url('orgs/%s/servers/%s' % (self.globals.config.agent.orgToken, self.globals.config.agent._id)))
        
        if API.is_success(response) == False:
            ret = self.error('Failed to unregister agent', response)
            
        return ret
    
    def authenticate(self, **kwargs):
        data = self.globals.config.agent.get_dict(['orgToken', 'agentVersion'])
        data['timestamp'] = int(time.time() * 1000)
        data['platform'] = {'isProxy': True if len(requests.utils.get_environ_proxies(self.get_url())) else False}
        data['platform'].update(self.globals.details)
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        response = self.exec_method('post', kwargs, self.get_url('agents/' + self.globals.config.agent._id + '/sessions'), data = json.dumps(data), headers = headers)    
        ret = self.status.SUCCESS
        
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
        response = self.exec_method('get', {}, self.get_url('agents/1'))
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.info('Config updation successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
            self.set_events(post_event = True)
        else:
            ret = self.error('Config updation failed. ', response)
            
        return ret
            
    def post_data(self, activity_id, data):
        response = self.exec_method('post', {'retry_count': 0}, self.get_url('agents/1/data/activities/' + activity_id), data = data)
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.debug('Sent activity (%s @ %d)' % (activity_id, data['timestamp']))
            self.set_events(post_event = True)
        else:
            ret = self.error('Failed to send activity (%s @ %d)' % (activity_id, data['timestamp']), response)
            
        return ret
    
    def logout(self):
        ret = self.status.SUCCESS
        
        if hasattr(self.globals.config.agent, '_id') == False or self.is_authenticated == False:
            return ret
        
        response = self.exec_method('delete', {'retry_count': 0, 'is_ignore_stop_event': True}, self.get_url('agents/1/sessions/1'))
        
        if API.is_success(response):
            _log.info('Logout successful')
        else:
            ret = self.error('Logout failed. ', response, True)

        return ret
    
    def get_agent_version(self):
        data = self.globals.config.agent.get_dict([('orgToken', ''), ('_id', ''), ('agentVersion', '')])
        url = self.get_url('orgs/%s/agents/%s/agentVersion' % (data['orgToken'], data['_id']))
        response = self.exec_method('get', {'retry_count': 0}, url, params = {'agentVersion': data['agentVersion']})
        
        if API.is_success(response):
            ret = response.json()['agentVersion']
        else:
            ret = self.error('Failed to get agent version ', response, True)
            ret == self.status.MISMATCH and self.stop()
        
        return ret
    
    def send_crash_report(self, data, **kwargs):
        orgToken, agentId = data['orgToken'], data['_id']
        del data['orgToken'], data['_id']
        response = self.exec_method('post', {'retry_count': 0}, self.get_url('orgs/%s/agents/%s/crashreport' % (orgToken, agentId)), data = data)    
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.info('Sent crash dump @ %d' % data['timestamp'])
            self.set_events(post_event = True)
        else:
            ret = self.error('Failed to send crash dump ', response, True)
        
        return ret
    
    def update_agent(self, event, version):
        if self.updater != None:
            return
        
        self.updater = ThreadEx(target = self.install_update, name = 'Updater', args = (version,))
        self.updater.daemon = True
        self.updater.start()
    
    def stop(self, stop_status = None):
        self.set_events(True, True)
        
        if stop_status != None:
            self.stop_status = stop_status
    
    def error(self, message, response, is_ignore_status = False):        
        API.print_error(message, response)    
        
        if response == None:
            is_ignore_status == False and self.globals.stop_event.is_set() == False and self.set_events(post_event = False)
            return self.status.NOT_CONNECTED
        
        status, ret, post_event, exec_func, args = response.status_code, self.status.UNKNOWN, True, None, ()
        
        try:
            code = response.json()['code']
        except:
            code = 0
            
        if status >= 500:
            post_event = False
            ret = self.status.NO_SERVICE
        elif status == 400:
            ret = self.status.BAD_REQUEST
        elif status == 401:
            if code == 200004:
                ret = self.status.MISMATCH
            else:
                if code == 200001 and self.stop_status == self.status.SUCCESS:
                    post_event = False
                    exec_func = connection.Connection().reconnect
                else:
                    post_event = None
                    exec_func = self.stop
                    
                ret = self.status.UNAUTHORIZED
        elif status == 404:
            post_event = None
            exec_func = self.stop
            args = (self.status.NOT_FOUND,)
            ret = self.status.NOT_FOUND
        elif status == 409:
            if code == 204011:
                ret = self.status.DATA_CONFLICT
            else:
                post_event = None
                exec_func = self.stop
                args = (self.status.SESSION_CONFLICT,)
                ret = self.status.SESSION_CONFLICT
                
        if is_ignore_status == False:
            self.set_events(post_event = post_event)
            exec_func and exec_func(*args)
            
        return ret
    
    def install_update(self, version):
        _log.info('Update found; Installing update %s' % version)
        format = 'curl -s %(download_url)s | bash /dev/stdin -a %(agent_id)s -o %(org_token)s -i "%(exe_path)s" -p "%(executable)s" -v %(version)s'
        format_spec = {
            'exe_path': exe_path, 
            'executable': sys.executable, 
            'org_token': self.globals.config.agent.orgToken, 
            'agent_id': self.globals.config.agent._id,
            'version': version, 
            'download_url': re.sub('://api', '://agent', self.get_url()) 
        }       
        subprocess.call(['bash', '-c', format % format_spec])
        time.sleep(60)
        _log.error('Failed to install update %s' % version)
        self.updater = None
        
