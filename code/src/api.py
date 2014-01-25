import time
import requests
from constructs import *

class Interface(requests.Session):    
    def __init__(self, config, stop_event, *args, **kwargs):
        super(Interface, self).__init__(*args, **kwargs)
        self.config = config
        self.stop_event = stop_event
        
        if hasattr(self.config.sealion, 'proxy'):
            self.proxies = self.config.sealion.proxy
            
    @staticmethod
    def is_success(response):
        status_code = response.status_code if response else 500
        return True if (status_code == 304 or (status_code >= 200 and status_code < 300)) else False
    
    @staticmethod
    def print_response(message, response):
        temp = 'Network issue' if response == None else response.json()['message']
        temp = (message + '; ' + temp) if len(message) else temp
        print temp
    
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
            
            try:
                response = method(*args, **kwargs)
            except Exception, e:
                print str(e)
                
            if response != None:
                break
                
            time.sleep(5)
        
        return response
    
    def register(self, retry_count = -1):
        data = self.config.agent.get_dict(['orgToken', 'name', 'category'])
        print 'Registering server in ' + self.config.agent.orgToken 
        response = self.exec_method('post', retry_count, self.get_url('agents'), data = data)    
        ret = False
        
        if Interface.is_success(response):
            print 'Registration succesful in ' + self.config.agent.orgToken
            self.config.agent.update(response.json())
            self.config.agent.save()
            ret = True
        else:
            Interface.print_response('Registration failed in ' + self.config.agent.orgToken, response)
        
        return True if ret else response
    
    def authenticate(self, retry_count = -1):
        data = self.config.agent.get_dict(['orgToken', 'agentVersion'])
        print 'Authenticating agent ' + self.config.agent._id
        response = self.exec_method('post', retry_count, self.get_url('agents/' + self.config.agent._id + '/sessions'), data = data)    
        ret = False
        
        if Interface.is_success(response):
            print 'Authenitcation succesful for agent ' + self.config.agent._id
            self.config.agent.update(response.json())
            self.config.agent.save()
            ret = True
        else:
            Interface.print_response('Authenitcation failed for agent ' + self.config.agent._id, response)
            self.stop_event.set()
        
        return True if ret else response
            
    def get_config(self, retry_count = -1):
        print 'Getting config for ' + self.config.agent._id
        response = self.exec_method('get', retry_count, self.get_url('agents/1'))
        ret = False
        
        if Interface.is_success(response):
            print 'Get config succesful for agent ' + self.config.agent._id
            self.config.agent.update(response.json())
            self.config.agent.save()
            ret = True
        else:
            Interface.print_response('Get config failed for agent ' + self.config.agent._id, response)
            
        return True if ret else response
            
    def post_data(self, activity_id, data, retry_count = 0):
        print 'Sending data ' + activity_id
        response = self.exec_method('post', retry_count, self.get_url('agents/1/data/activities/' + activity_id), data = data)
        ret = False
        
        if Interface.is_success(response):
            print 'Send succesful for data ' + activity_id
            ret = True
        else:
            Interface.print_response('Send failed for data ' + activity_id, response)
            response and self.stop_event.set()
            
        return True if ret else response
    
    def logout(self):
        print 'Logging out agent ' + self.config.agent._id
        response = self.exec_method('delete', 0, self.get_url('agents/1/sessions/1'))
        ret = False
        
        if Interface.is_success(response):
            print 'Logout succesful for agent ' + self.config.agent._id
            ret = True
        else:
            Interface.print_response('Logout failed for agent ' + self.config.agent._id, response)
            
        return True if ret else response