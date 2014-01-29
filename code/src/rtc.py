import logging
from socketio_client import SocketIO, BaseNamespace
import threading

_log = logging.getLogger(__name__)

class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        _log.debug('Socket-io connected')
        self.api.ping()
        
    def on_disconnect(self):
        _log.debug('Socket-io disconnected')

    def on_activity_updated(self, *args):
        _log.debug('Socket-io received  activity_updated event')
        self.api.get_config()

    def on_activitylist_in_category_updated(self, *args):
        _log.debug('Socket-io received  activitylist_in_category_updated event')
        self.api.get_config()

    def on_agent_removed(self, *args):
        _log.debug('Socket-io received  agent_removed event')
        self.api.stop()

    def on_org_token_resetted(self, *args):
        _log.debug('Socket-io received  org_token_resetted event')
        self.api.stop()

    def on_server_category_changed(self, *args):
        _log.debug('Socket-io received  server_category_changed event')
        self.api.get_config()

    def on_activity_deleted(self, *args):
        _log.debug('Socket-io received  activity_deleted event')
        self.api.get_config()
        
class Interface(threading.Thread):    
    def __init__(self, api):
        threading.Thread.__init__(self)
        self.api = api
        self.sio = None
        
    def connect(self):
        SocketIONamespace.api = self.api
        kwargs = {
            'Namespace': SocketIONamespace,
            'cookies': self.api.cookies,
            'proxies': self.api.proxies
        }
        
        if len(self.api.proxies):
            _log.info('Proxy detected; forcing xhr-polling for socket-io')
            kwargs['transports'] = ['xhr-polling']
        
        _log.debug('Waiting for socket-io connection')
        self.sio = SocketIO(self.api.get_url(), **kwargs)
        return self
    
    def stop(self):
        if self.sio != None:
            _log.debug('Disconnecting socket-io')
            self.sio.disconnect()

    def run(self):       
        _log.debug('Starting up socket-io')
        self.sio.wait()                
        _log.debug('Shutting down socket-io')
