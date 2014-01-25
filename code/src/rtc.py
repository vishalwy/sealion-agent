from socketio_client import SocketIO, BaseNamespace
import threading

class SocketIONamespace(BaseNamespace):
    def on_connect(self):
        print '[connected]'
        
    def on_disconnect(self):
        print '[disconnected]'

    def on_activity_updated(self, *args):
        print '[activity_updated]'

    def on_activitylist_in_category_updated(self, *args):
        print '[activitylist_in_category_updated]'

    def on_agent_removed(self, *args):
        print '[agent_removed]'

    def on_org_token_resetted(self, *args):
        print '[org_token_resetted]'

    def on_server_category_changed(self, *args):
        print '[server_category_changed]'

    def on_activity_deleted(self, *args):
        print '[activity_deleted]'
        
class Interface(threading.Thread):    
    def __init__(self, api, stop_event):
        threading.Thread.__init__(self)
        self.api = api
        self.stop_event = stop_event
        
    def connect(self):
        self.sio = SocketIO(self.api.get_url(), Namespace = SocketIONamespace, cookies = self.api.cookies, proxies = self.api.proxies)
        return self

    def run(self):        
        while 1:
            self.sio.wait(5)
            
            if self.stop_event.is_set():
                self.sio.disconnect()
                break

#check for termination condition