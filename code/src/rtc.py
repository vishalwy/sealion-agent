import pdb
from lib.socketio_client import SocketIO, BaseNamespace
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
    def __init__(self, api):
        threading.Thread.__init__(self)
        self.api = api
        
    def connect(self):
        self.io = SocketIO(self.api.get_url(), Namespace=SocketIONamespace, cookies=self.api.cookies, proxies=self.api.proxies)
        return self

    def run(self):        
        while 1:
            self.io.wait(5)

#check for termination condition