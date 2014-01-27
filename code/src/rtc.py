import logging
from socketio_client import SocketIO, BaseNamespace
import threading

_log = logging.getLogger(__name__)

class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        _log.debug('Connected ' + str(rtc))
        self.rtc.api.ping()
        
    def on_disconnect(self):
        _log.debug('Disconnected ' + str(rtc))

    def on_activity_updated(self, *args):
        _log.debug('Heard activity_updated ' + str(rtc))
        self.rtc.api.get_config()

    def on_activitylist_in_category_updated(self, *args):
        _log.debug('Heard activitylist_in_category_updated ' + str(rtc))
        self.rtc.api.get_config()

    def on_agent_removed(self, *args):
        _log.debug('Heard agent_removed ' + str(rtc))
        self.rtc.api.stop_event.set()

    def on_org_token_resetted(self, *args):
        _log.debug('Heard org_token_resetted ' + str(rtc))
        self.rtc.api.stop_event.set()

    def on_server_category_changed(self, *args):
        _log.debug('Heard server_category_changed ' + str(rtc))
        self.rtc.api.get_config()

    def on_activity_deleted(self, *args):
        _log.debug('Heard activity_deleted ' + str(rtc))
        self.rtc.api.get_config()
        
class Interface(threading.Thread):    
    def __init__(self, api):
        threading.Thread.__init__(self)
        self.api = api
        
    def connect(self):
        SocketIONamespace.rtc = self
        self.sio = SocketIO(self.api.get_url(), Namespace = SocketIONamespace, cookies = self.api.cookies, proxies = self.api.proxies)
        return self

    def run(self):       
        _log.debug('Starting up socket io ' + str(self))
        
        while 1:
            self.sio.wait(5)
            
            if self.api.stop_event.is_set():
                self.sio.disconnect()
                break
                
        _log.debug('Shutting down socket io ' + str(self))
