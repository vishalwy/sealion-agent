import logging
import time
import requests
import globals
import api
from socketio_client import SocketIO, BaseNamespace
from constructs import *

_log = logging.getLogger(__name__)

class SocketIONamespace(BaseNamespace):
    def initialize(self):
        self.globals = globals.Interface()
        self.api = api.Interface()
    
    def on_connect(self):        
        _log.info('Socket-io connected')
        self.rtc.update_heartbeat()
        
        if self.rtc.is_stop == True or self.globals.stop_event.is_set():
            self.rtc.stop()
            return
        
        self.api.ping()
        self.rtc.is_disconnected and self.api.get_config()
        self.rtc.is_disconnected = False
        
    def on_disconnect(self):
        _log.info('Socket-io disconnected')
        self.rtc.update_heartbeat()
        self.rtc.is_disconnected = True
        
    def on_heartbeat(self):
        _log.debug('Socket-io heartbeat')
        self.rtc.update_heartbeat()

    def on_activity_updated(self, *args):
        _log.info('Socket-io received activity_updated event')
        self.rtc.update_heartbeat()
        self.api.get_config()

    def on_activitylist_in_category_updated(self, *args):
        _log.info('Socket-io received activitylist_in_category_updated event')
        self.rtc.update_heartbeat()
        self.api.get_config()

    def on_agent_removed(self, *args):
        _log.info('Socket-io received agent_removed event')
        self.rtc.update_heartbeat()
        
        try:
            if args[0].get('servers'):
                (self.globals.config.agent._id in args[0]['servers']) and self.api.stop(self.api.status.NOT_FOUND)
            else:
                self.api.stop(self.api.status.NOT_FOUND)
        except:
            pass    

    def on_org_token_resetted(self, *args):
        _log.info('Socket-io received org_token_resetted event')
        self.api.stop()

    def on_server_category_changed(self, *args):
        _log.info('Socket-io received server_category_changed event')
        self.rtc.update_heartbeat()
        
        try:
            if args[0].get('servers'):
                (self.globals.config.agent._id in args[0]['servers']) and self.api.get_config()
            else:
                self.api.get_config()
        except:
            pass

    def on_activity_deleted(self, *args):
        _log.info('Socket-io received activity_deleted event')
        self.rtc.update_heartbeat()
        
        try:
            (args[0]['activity'] in self.globals.config.agent.activities) and self.api.get_config()
        except:
            pass
        
    def on_upgrade_agent(self, *args):
        _log.info('Socket-io received upgrade_agent event')
        self.rtc.update_heartbeat()
        
        try:
            args[0]['agentVersion'] != self.globals.config.agent.agentVersion and self.api.update_agent()
        except:
            pass
        
class RTC(ThreadEx):    
    def __init__(self):
        ThreadEx.__init__(self)
        self.api = api.Interface()
        self.sio = None
        self.is_stop = False
        self.daemon = True
        self.is_disconnected = False
        self.update_heartbeat()
        
    def connect(self):
        SocketIONamespace.rtc = self
        kwargs = {
            'Namespace': SocketIONamespace,
            'cookies': self.api.cookies
        }
        
        if len(requests.utils.get_environ_proxies(self.api.get_url())):
            _log.info('Proxy detected; forcing xhr-polling for socket-io')
            kwargs['transports'] = ['xhr-polling']
            kwargs['stream'] = True
        
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
        if self.sio == None or self.sio.heartbeat_timeout == -1:
            return True
        
        t = int(time.time())        
        is_beating = True if t - self.last_heartbeat < self.sio.heartbeat_timeout else False
        self.update_heartbeat()
        return is_beating

    def exe(self):       
        _log.debug('Starting up socket-io')
        
        while 1:
            try:
                self.sio.wait()
            except Exception as e:
                _log.debug(str(e))
            
            if self.is_stop == True or globals.Interface().stop_event.is_set():
                break
                
            self.connect()
        
        _log.debug('Shutting down socket-io')

Interface = RTC