import sys
import logging
import requests
import tempfile
import subprocess
import time
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
    UNAUTHERIZED = 7
    SESSION_CONFLICT = 8
    UNKNOWN = -1

class API(SingletonType('APIMetaClass', (object, ), {}), requests.Session):    
    status = Status
    
    def __init__(self, *args, **kwargs):
        requests.Session.__init__(self, *args, **kwargs)
        self.globals = globals.Interface()
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
        
    def is_ok(self, status):
        if status < self.status.BAD_REQUEST:
            return True
        
        return False
    
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
        response, i = None, 0
        
        while retry_count == -1 or i <= retry_count:                
            if i > 0:
                self.globals.stop_event.wait(retry_interval)
                
            if is_ignore_stop_event == False and self.globals.stop_event.is_set():
                break
            
            try:
                response = method(timeout = 10, *args, **kwargs)
            except Exception as e:
                _log.error(str(e)) 
                
            if response != None:
                self.is_conn_err == True and _log.info('Reconnected')
                self.is_conn_err = False
                break
                
            i += 0 if retry_count == -1 and i > 0 else 1
            
        if response == None and self.is_authenticated == True:
            self.is_conn_err = True
        
        return response
    
    def ping(self):
        self.set_events(post_event = True)
    
    def register(self, **kwargs):
        data = self.globals.config.agent.get_dict(['orgToken', 'name', 'category'])
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
        response = self.exec_method('delete', {'retry_count': 2}, self.get_url('orgs/%s/servers/%s' % (self.globals.config.agent.orgToken, self.globals.config.agent._id)))
        ret = self.status.SUCCESS
        
        if API.is_success(response) == False:
            ret = self.error('Failed to register agent', response)
            
        return ret
    
    def authenticate(self, **kwargs):
        data = self.globals.config.agent.get_dict(['orgToken', 'agentVersion'])
        data['timestamp'] = int(time.time() * 1000)
        response = self.exec_method('post', kwargs, self.get_url('agents/' + self.globals.config.agent._id + '/sessions'), data = data)    
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.info('Authentication successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
            self.is_authenticated = True
            self.set_events(post_event = True)
        else:
            ret = self.error('Failed to authenticate agent', response)
        
        return ret
            
    def get_config(self):
        response = self.exec_method('get', {}, self.get_url('agents/1'))
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.info('Config updation successful')
            self.globals.config.agent.update(response.json())
            self.globals.config.agent.save()
        else:
            ret = self.error('Failed to get config', response)
            
        return ret
            
    def post_data(self, activity_id, data):
        response = self.exec_method('post', {'retry_count': 0}, self.get_url('agents/1/data/activities/' + activity_id), data = data)
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            self.set_events(post_event = True)
            _log.debug('Sent activity(%s @ %d)' % (activity_id, data['timestamp']))
        else:
            ret = self.error('Failed to send activity(%s @ %d)' % (activity_id, data['timestamp']), response)
            
        return ret
    
    def logout(self):
        ret = self.status.SUCCESS
        
        if hasattr(self.globals.config.agent, '_id') == False or self.is_authenticated == False:
            return ret
        
        response = self.exec_method('delete', {'retry_count': 0, 'is_ignore_stop_event': True}, self.get_url('agents/1/sessions/1'))
        
        if API.is_success(response):
            _log.info('Logout successful')
        else:
            ret = self.error('Failed to logout agent', response)

        return ret
    
    def get_agent_version(self):
        response = self.exec_method('get', {'retry_count': 0}, self.get_url('agents/agentVersion'), params = {'agentVersion': self.globals.config.agent.agentVersion})
        
        if API.is_success(response):
            ret = response.json()['agentVersion']
        else:
            ret = self.error('Failed to get agent version', response, True)
        
        return ret
    
    def send_crash_report(self, data, **kwargs):
        orgToken, agentId = data['orgToken'], data['_id']
        del data['orgToken'], data['_id']
        response = self.exec_method('post', {'retry_count': 0, 'retry_interval': 30}, self.get_url('orgs/%s/agents/%s/crashreport' % (orgToken, agentId)), data = data)    
        ret = self.status.SUCCESS
        
        if API.is_success(response):
            _log.info('Sent crash dump @ %d' % data['timestamp'])
        else:
            ret = self.error('Failed to send crash dump', response, True)
        
        return ret
    
    def update_agent(self, event = None):
        if self.updater != None:
            return
        
        self.updater = ThreadEx(target = self.download_update)
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
        
        status = response.status_code
        
        try:
            code = response.json()['code']
        except:
            code = 0
            
        if status >= 500:
            is_ignore_status == False and self.set_events(post_event = False)
            return self.status.NO_SERVICE
        elif status == 400:
            is_ignore_status == False and self.stop()
            return self.status.BAD_REQUEST
        elif status == 401:
            if code == 200004:
                return self.status.MISMATCH
            else:
                if is_ignore_status == False:
                    if code == 200001 and self.stop_status == self.status.SUCCESS:
                        self.set_events(post_event = False)
                        connection.Interface().reconnect()
                    else:
                        self.stop()
                    
                return self.status.UNAUTHERIZED
        elif status == 404:
            is_ignore_status == False and self.stop(self.status.NOT_FOUND)
            return self.status.NOT_FOUND
        elif status == 409:
            if code == 204011:
                return self.status.DATA_CONFLICT
            else:
                is_ignore_status == False and self.stop(self.status.SESSION_CONFLICT)
                return self.status.SESSION_CONFLICT
        
        return self.status.UNKNOWN
    
    def download_update(self):
        exe_path = self.globals.exe_path
        url = self.globals.config.agent.updateUrl
        temp_dir = tempfile.mkdtemp()
        temp_dir = temp_dir[:-1] if temp_dir[len(temp_dir) - 1] == '/' else temp_dir
        filename = '%s/%s' % (temp_dir, url.split('/')[-1])
        _log.info('Update found; downloading to %s' % filename)
        f = open(filename, 'wb')
        response = self.exec_method('get', {}, url, stream = True)
        
        if API.is_success(response) == False:
            self.error('Failed to download the update', response, True)
            f and f.close()
            self.updater = None
            return
            
        is_completed = False
        
        try:
            for chunk in response.iter_content(chunk_size = 1024):
                if self.globals.stop_event.is_set():
                    _log.info('Updater received stop event')
                    break

                if chunk:
                    f.write(chunk)
                    f.flush()

            is_completed = True
        except Exception as e:
            _log.error(str(e))
        finally:
            f.close()
            
        if is_completed == True:
            _log.info('Update succesfully downloaded to %s' % filename)
        else:
            _log.info('Aborted downloading update')
            self.updater = None
            return
        
        _log.debug('Extracting %s to %s' % (filename, temp_dir))
        
        if subprocess.call(['tar', '-xf', "%s" % filename, '--directory=%s' % temp_dir]):
            _log.error('Failed to extract update %s' % filename)
            self.updater = None
            return
            
        _log.info('Installing update')
        subprocess.Popen('"%(temp_dir)s/sealion-agent/install.sh" -i "%(exe_path)s" -p "%(executable)s" && rm -rf "%(temp_dir)s"' % {'temp_dir': temp_dir, 'exe_path': exe_path, 'executable': sys.executable}, shell=True)

Interface = API