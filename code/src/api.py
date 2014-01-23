import pdb
import time
from lib import requests
from constructs import *

class Interface(requests.Session):    
    def __init__(self, config, *args, **kwargs):
        super(Interface, self).__init__(*args, **kwargs)
        self.config = config
        
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
    
    def register(self):
        data = self.config.agent.get_dict(['orgToken', 'name', 'category'])
        response, i = None, 0
        print 'Registering server in ' + self.config.agent.orgToken 
        
        while i < 5:
            try:
                response = self.post(self.get_url('agents'), data = data)
            except Exception, e:
                print str(e)
                
            if response != None:
                break
                
            time.sleep(5)
            i += 1
            
        ret = False
        
        if Interface.is_success(response):
            print 'Registration succesful in ' + self.config.agent.orgToken
            self.config.agent.update(response.json())
            self.config.agent.save()
            ret = True
        else:
            Interface.print_response('Registration failed in ' + self.config.agent.orgToken, response)
        
        
        return ret
    
    def authenticate(self, is_retry_infinite = False):
        data = self.config.agent.get_dict(['orgToken', 'agentVersion'])
        
        response, i = None, 0
        print 'Authenticating agent ' + self.config.agent._id
        
        while i < 5:
            try:
                response = self.post(self.get_url('agents/' + self.config.agent._id + '/sessions'), data = data)
            except Exception, e:
                print str(e)
                
            if response != None:
                break
                
            time.sleep(5)
            i += 0 if is_retry_infinite == True else 1
            
        ret = False
        
        if response == None:
            print 'Authenitcation failed for agent ' + self.config.agent._id + '; Network issue'
        elif Interface.is_success(response):
            print 'Authenitcation succesful for agent ' + self.config.agent._id
            self.config.agent.update({'activities': response.json()['activities']})
            self.config.agent.save()
            ret = True
        elif response.status_code == 404:
            print 'Authenitcation failed for agent ' + self.config.agent._id + '; Cannot find agent'
        elif response.status_code == 401:
            print 'Authenitcation failed for agent ' + self.config.agent._id + '; Unautherized'
        else:
            print 'Something went wrong while attempting to authenitcate agent ' + self.config.agent._id
        
        return ret
    
    def post_data(self, activity_id, data):
        response = None
        print 'Sending data ' + activity_id
        
        try:
            response = self.post(self.get_url('agents/1/data/activities/' + activity_id), data = data)
        except Exception, e:
            print str(e)
            
        
            
        
            
        
    
    
    
    
    
    