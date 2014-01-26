import pdb
from socketio_client import SocketIO, BaseNamespace
import threading

class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        print '[connected]'
        self.api.ping()
        
    def on_disconnect(self):
        print '[disconnected]'

    def on_activity_updated(self, *args):
        print '[activity_updated]'
        self.api.get_config()

    def on_activitylist_in_category_updated(self, *args):
        print '[activitylist_in_category_updated]'
        self.api.get_config()

    def on_agent_removed(self, *args):
        print '[agent_removed]'
        self.api.stop_event.set()

    def on_org_token_resetted(self, *args):
        print '[org_token_resetted]'
        self.api.stop_event.set()

    def on_server_category_changed(self, *args):
        print '[server_category_changed]'
        self.api.get_config()

    def on_activity_deleted(self, *args):
        print '[activity_deleted]'
        self.api.get_config()
        
class Interface(threading.Thread):    
    def __init__(self, api):
        threading.Thread.__init__(self)
        self.api = api
        
    def connect(self):
        SocketIONamespace.api = self.api
        self.sio = SocketIO(self.api.get_url(), Namespace = SocketIONamespace, cookies = self.api.cookies, proxies = self.api.proxies)
        return self

    def run(self):        
        while 1:
            self.sio.wait(5)
            
            if self.api.stop_event.is_set():
                self.sio.disconnect()
                break

#check for termination condition