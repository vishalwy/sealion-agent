import logging
import time
import requests
import threading
from constructs import *

_log = logging.getLogger(__name__)

class Status(EmptyClass):
    SUCCESS = 0
    NOT_CONNECTED = 1
    NO_SERVICE = 2
    DATA_CONFLICT = 3
    MISMATCH = 4
    BAD_REQUEST = 5
    NOT_FOUND = 6
    UNAUTHERIZED = 7
    SESSION_CONFLICT = 8
    UNKNOWN = -1

class Interface(requests.Session):    
    status = Status
    
    def __init__(self, config, stop_event, *args, **kwargs):
        super(Interface, self).__init__(*args, **kwargs)
        self.config = config
        self.stop_event = stop_event
        self.post_event = threading.Event()

        if hasattr(self.config.sealion, 'proxy'):
            self.proxies = self.config.sealion.proxy
            
    @staticmethod
    def is_success(response):
        status_code = response.status_code if response else 500
        return True if (status_code == 304 or (status_code >= 200 and status_code < 300)) else False
    
    @staticmethod
    def print_error(message, response):
        temp = 'Network issue'
        
        if response != None:
            try:
                temp = response.json()['message']
            except:
                temp = 'Error ' + str(response.status_code)
        
        temp = (message + '; ' + temp) if len(message) else temp
        _log.error(temp)
        
    def is_ok(self, status):
        if status < self.status.BAD_REQUEST:
            return True
        
        return False
    
    def is_not_connected(self, status):
        if status == self.status.NOT_CONNECTED or status == self.status.NO_SERVICE:
            return True
        
        return False
    
    def get_url(self, path = ''):
        path.strip()
        
        if len(path):
            path = path if path[0] == '/' else ('/' + path)
                  
        return self.config.agent.apiUrl + path
    
    def exec_method(self, method, retry_count = -1, *args, **kwargs):
        method = getattr(self, method)
        response, i = None, 0
        
        while retry_count == -1 or i <= retry_count:
            if self.stop_event.is_set():
                break
                
            if i > 0:
                time.sleep(5)
            
            try:
                response = method(*args, **kwargs)
            except Exception, e:
                _log.error(str(e)) 
                
            if response != None:
                break
                
            i += 1
        
        return response
    
    def ping(self):
        _log.debug('Setting post event')
        self.post_event.set()
    
    def register(self, retry_count = -1):
        data = self.config.agent.get_dict(['orgToken', 'name', 'category'])
        response = self.exec_method('post', retry_count, self.get_url('agents'), data = data)    
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.info('Registration successful')
            self.config.agent.update(response.json())
            self.config.agent.save()
        else:
            ret = self.error('Registration failed', response)
        
        return ret
    
    def authenticate(self, retry_count = -1):
        data = self.config.agent.get_dict(['orgToken', 'agentVersion'])
        response = self.exec_method('post', retry_count, self.get_url('agents/' + self.config.agent._id + '/sessions'), data = data)    
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.info('Authentication successful')
            self.config.agent.update(response.json())
            self.config.agent.save()
            _log.debug('Setting post event')
            self.post_event.set()
        else:
            ret = self.error('Authenitcation failed', response)
        
        return ret
            
    def get_config(self, retry_count = -1):
        response = self.exec_method('get', retry_count, self.get_url('agents/1'))
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.info('Config updation successful')
            self.config.agent.update(response.json())
            self.config.agent.save()
        else:
            ret = self.error('Get config failed', response)
            
        return ret
            
    def post_data(self, activity_id, data, retry_count = 0):
        response = self.exec_method('post', retry_count, self.get_url('agents/1/data/activities/' + activity_id), data = data)
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.debug('Sent ' + activity_id + ' @ ' + str(data['timestamp']))
            _log.debug('Setting post event')
            self.post_event.set()
        else:
            ret = self.error('Send failed for ' + activity_id + ' @ ' + str(data['timestamp']), response)
            
        return ret
    
    def logout(self):
        response = self.exec_method('delete', 0, self.get_url('agents/1/sessions/1'))
        ret = self.status.SUCCESS
        
        if Interface.is_success(response) == False:
            ret = self.error('Logout failed for agent ' + self.config.agent._id, response)

        return ret
    
    def stop(self):
        _log.debug('Setting stop and post events')
        self.stop_event.set()
        self.post_event.set()
    
    def error(self, message, response):        
        Interface.print_error(message, response)    
        
        if response == None:
            _log.debug('Resetting post event')
            self.post_event.clear()
            return self.status.NOT_CONNECTED
        
        status = response.status_code
        
        try:
            code = response.json()['code']
        except:
            code = 0
            
        if status >= 500:
            _log.debug('Resetting post event')
            self.post_event.clear()
            return self.status.NO_SERVICE
        elif status == 400:
            self.stop()
            return self.status.BAD_REQUEST
        elif status == 401:
            if code == 200004:
                return self.status.MISMATCH
            else:
                self.stop()
                return self.status.UNAUTHERIZED
        elif status == 404:
            self.stop()
            return self.status.NOT_FOUND
        elif status == 409:
            if code == 204011:
                return self.status.DATA_CONFLICT
            else:
                self.stop()
                return self.status.SESSION_CONFLICT
        
        return self.status.UNKNOWN

        