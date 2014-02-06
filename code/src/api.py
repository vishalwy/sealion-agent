import logging
import requests
import threading
import tempfile
import subprocess
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
        self.proxies = requests.utils.get_environ_proxies(self.get_url())
        self.stop_status = Status.SUCCESS
        self.is_authenticated = False
        self.updater = None
        
        if hasattr(self.config.sealion, 'proxy'):
            self.proxies.update(self.config.sealion.proxy)
            
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
        
    def is_ok(self, status):
        if status < self.status.BAD_REQUEST:
            return True
        
        return False
    
    def is_not_connected(self, status):
        if status == self.status.NOT_CONNECTED or status == self.status.NO_SERVICE:
            return True
        
        return False
    
    def set_events(self, stop_event = None, post_event = None):
        if stop_event == True and self.stop_event.is_set() == False:
            _log.debug('Setting stop event')
            self.stop_event.set()
        elif stop_event == False and self.stop_event.is_set() == True:
            _log.debug('Resetting stop event')
            self.stop_event.clear()
        
        if post_event == True and self.post_event.is_set() == False:
            _log.debug('Setting post event')
            self.post_event.set()
        elif post_event == False and self.post_event.is_set() == True:
            _log.debug('Resetting post event')
            self.post_event.clear()
    
    def get_url(self, path = ''):
        path.strip()
        
        if len(path):
            path = path if path[0] == '/' else ('/' + path)
                  
        return self.config.agent.apiUrl + path
    
    def exec_method(self, method, retry_count = -1, retry_interval = 5, *args, **kwargs):
        method = getattr(self, method)
        response, i = None, 0
        
        while retry_count == -1 or i <= retry_count:                
            if i > 0:
                self.stop_event.wait(retry_interval)
                
            if self.stop_event.is_set():
                break
            
            try:
                response = method(timeout = 10, *args, **kwargs)
            except Exception, e:
                _log.error(str(e)) 
                
            if response != None:
                break
                
            i += 1
        
        return response
    
    def ping(self):
        self.set_events(post_event = True)
    
    def register(self, retry_count = -1, retry_interval = 5):
        data = self.config.agent.get_dict(['orgToken', 'name', 'category'])
        response = self.exec_method('post', retry_count, retry_interval, self.get_url('agents'), data = data)    
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.info('Registration successful')
            self.config.agent.update(response.json())
            self.config.agent.save()
        else:
            ret = self.error('Failed to register agent', response)
        
        return ret
    
    def unregister(self):
        response = self.exec_method('delete', 2, 5, self.get_url('orgs/%s/servers/%s' % (self.config.agent.orgToken, self.config.agent._id)))
        ret = self.status.SUCCESS
        
        if Interface.is_success(response) == False:
            ret = self.error('Failed to register agent', response)
            
        return ret
    
    def authenticate(self, retry_count = -1, retry_interval = 5):
        data = self.config.agent.get_dict(['orgToken', 'agentVersion'])
        response = self.exec_method('post', retry_count, retry_interval, self.get_url('agents/' + self.config.agent._id + '/sessions'), data = data)    
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.info('Authentication successful')
            self.config.agent.update(response.json())
            self.config.agent.save()
            self.is_authenticated = True
            self.set_events(post_event = True)
        else:
            ret = self.error('Failed to authenticate agent', response)
        
        return ret
            
    def get_config(self, retry_count = -1, retry_interval = 5):
        response = self.exec_method('get', retry_count, retry_interval, self.get_url('agents/1'))
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.info('Config updation successful')
            self.config.agent.update(response.json())
            self.config.agent.save()
        else:
            ret = self.error('Failed to get config', response)
            
        return ret
            
    def post_data(self, activity_id, data, retry_count = 0, retry_interval = 5):
        response = self.exec_method('post', retry_count, retry_interval, self.get_url('agents/1/data/activities/' + activity_id), data = data)
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.debug('Sent activity(%s @ %d)' % (activity_id, data['timestamp']))
            self.set_events(post_event = True)
        else:
            ret = self.error('Failed to send activity(%s @ %d)' % (activity_id, data['timestamp']), response)
            
        return ret
    
    def logout(self):
        ret = self.status.SUCCESS
        
        if hasattr(self.config.agent, '_id') == False:
            return ret
        
        self.stop_event.clear()
        response = self.exec_method('delete', 0, 0, self.get_url('agents/1/sessions/1'))
        
        if Interface.is_success(response):
            _log.debug('Logout successful')
        else:
            ret = self.error('Failed to logout agent ' + self.config.agent._id, response)

        return ret
    
    def send_crash_report(self, data, retry_count = 3, retry_interval = 30):
        orgToken, agentId = data['orgToken'], data['_id']
        del data['orgToken'], data['_id']
        response = self.exec_method('post', retry_count, retry_interval, self.get_url('/orgs/%s/agents/%s/crashreport' % (orgToken, agentId)), data = data)    
        ret = self.status.SUCCESS
        
        if Interface.is_success(response):
            _log.debug('Sent crash dump @ ' + data['timestamp'])
        else:
            ret = self.error('Failed to send crash dump', response)
        
        return ret
    
    def update_agent(self, exe_path):
        if self.updater != None:
            return
        
        self.updater = ExceptionThread(target = self.download_file, args=(exe_path,))
        self.updater.start()
    
    def stop(self, stop_status = None):
        self.set_events(True, True)
        
        if stop_status != None:
            self.stop_status = stop_status
    
    def error(self, message, response):        
        Interface.print_error(message, response)    
        
        if response == None:
            self.set_events(post_event = False)
            return self.status.NOT_CONNECTED
        
        status = response.status_code
        
        try:
            code = response.json()['code']
        except:
            code = 0
            
        if status >= 500:
            self.set_events(post_event = False)
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
            self.stop(self.status.NOT_FOUND)
            return self.status.NOT_FOUND
        elif status == 409:
            if code == 204011:
                return self.status.DATA_CONFLICT
            else:
                self.stop(self.status.SESSION_CONFLICT)
                return self.status.SESSION_CONFLICT
        
        return self.status.UNKNOWN
    
    def download_file(self, exe_path):
        url = self.config.agent.updateUrl
        temp_dir = tempfile.gettempdir()
        temp_dir = temp_dir + '/' if temp_dir[len(temp_dir) - 1] != '/' else temp_dir
        filename = temp_dir + url.split('/')[-1]
        
        _log.info('Update found; downloading to %s' % filename)
        
        try:
            response = requests.get(url, stream = True)
        except Exception, e:
            _log.error('Failed to download the update %s' % str(e))
            self.updater = None
            return
            
        is_completed = False
        
        with open(filename, 'wb') as f:
            try:
                for chunk in response.iter_content(chunk_size = 1024):
                    if self.stop_event.is_set():
                        _log.info('Updater received stop event')
                        break

                    if chunk:
                        f.write(chunk)
                        f.flush()

                is_completed = True
            except Exception, e:
                _log.error(str(e))
            
        if is_completed == True:
            _log.info('Update succesfully downloaed to %s' % filename)
        else:
            _log.info('Aborted downloading update')
            self.updater = None
            return
        
        try:
            _log.debug('Extracting %s to %s', (filename, temp_dir))
            subprocess.call(['tar', '-xf', filename, '--directory=%s' % temp_dir])
            _log.info('Installing update')
            subprocess.Popen([temp_dir + 'sealion-agent/install.sh', '-i', exe_path])
        except Exception, e:
            _log.error('Failed to update; ' + str(e))
            self.updater = None
