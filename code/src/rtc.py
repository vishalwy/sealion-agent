import logging
import time
import requests
from socketio_client import SocketIO, BaseNamespace
from constructs import *

_log = logging.getLogger(__name__)

class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        _log.info('Socket-io connected')
        self.rtc.update_heartbeat()
        self.rtc.api.ping()
        self.rtc.is_disconnected and self.rtc.api.get_config()
        self.rtc.is_disconnected = False
        
    def on_disconnect(self):
        self.rtc.is_disconnected = True
        _log.info('Socket-io disconnected')
        
    def on_heartbeat(self):
        _log.debug('Socket-io heartbeat')
        self.rtc.update_heartbeat()

    def on_activity_updated(self, *args):
        _log.info('Socket-io received  activity_updated event')
        self.rtc.update_heartbeat()
        self.rtc.api.get_config()

    def on_activitylist_in_category_updated(self, *args):
        _log.info('Socket-io received  activitylist_in_category_updated event')
        self.rtc.update_heartbeat()
        self.rtc.api.get_config()

    def on_agent_removed(self, *args):
        _log.info('Socket-io received  agent_removed event')
        self.rtc.api.stop(self.rtc.api.status.NOT_FOUND)

    def on_org_token_resetted(self, *args):
        _log.info('Socket-io received  org_token_resetted event')
        self.rtc.api.stop()

    def on_server_category_changed(self, *args):
        _log.info('Socket-io received  server_category_changed event')
        self.rtc.update_heartbeat()
        self.rtc.api.get_config()

    def on_activity_deleted(self, *args):
        _log.info('Socket-io received  activity_deleted event')
        self.rtc.update_heartbeat()
        self.rtc.api.get_config()
        
class Interface(ThreadEx):    
    def __init__(self, api):
        ThreadEx.__init__(self)
        self.api = api
        self.sio = None
        self.last_heartbeat = int(time.time())
        self.is_stop = False
        self.is_disconnected = False
        
    def connect(self):
        SocketIONamespace.rtc = self
        kwargs = {
            'Namespace': SocketIONamespace,
            'cookies': self.api.cookies
        }
        
        if len(requests.utils.get_environ_proxies(self.api.get_url())):
            _log.info('Proxy detected; forcing xhr-polling for socket-io')
            kwargs['transports'] = ['xhr-polling']
        
        _log.debug('Waiting for socket-io connection')
        self.sio = SocketIO(self.api.get_url(), **kwargs)
        return self
    
    def stop(self):
        self.is_stop = True
        
        if self.sio != None:
            _log.debug('Disconnecting socket-io')
            
            try:
                self.sio.disconnect()
            except:
                pass
            
    def update_heartbeat(self):
        self.last_heartbeat = int(time.time())
        
    def is_heartbeating(self):
        if self.sio.heartbeat_timeout == -1:
            return True
        
        return (int(time.time()) - self.last_heartbeat) < self.sio.heartbeat_timeout

    def exe(self):       
        _log.debug('Starting up socket-io')
        
        while 1:
            try:
                self.sio.wait()
            except Exception as e:
                _log.debug(str(e))
            
            if self.is_stop == True:
                break
                
            self.connect()
        
        _log.debug('Shutting down socket-io')
