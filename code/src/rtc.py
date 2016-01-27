"""
Abstracts the real time communication between agent and the api server using socket-io
Implements SocketIONamespace, SocketIOHandShakeError, RTC and create_session
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import time
import universal
import api
import connection
from socketio_client import SocketIO, BaseNamespace
from constructs import *

_log = logging.getLogger(__name__)  #module level logging
session = None  #RTC session for agent

class SocketIOHandShakeError(Exception):
    """
    Exception to be raised when socket-io raises handshake error.
    """
    
    pass

class SocketIONamespace(BaseNamespace):
    """
    Socket-io namespace for handling various events.
    """
    
    def initialize(self):
        """
        Method gets called when socket-io is initialized.
        """
        
        self.univ = universal.Universal()  #save the reference to Universal for optimized access
    
    def on_connect(self):        
        """
        Method gets called when socket-io connects.
        """
        
        _log.info('SocketIO connected')
        self.rtc.update_heartbeat()
        
        if self.rtc.is_stop == True or self.univ.stop_event.is_set():  #do we need to stop
            self.rtc.stop()
            return
        
        api.session.ping()  #ping api session so that any bloking post data operation can continue
        self.rtc.is_disconnected and api.session.get_config()  #if it is a reconnect, get the config
        self.rtc.is_disconnected = False
        
    def on_disconnect(self):
        """
        Method gets called when socket-io disconnects.
        """
        
        _log.info('SocketIO disconnected')
        self.rtc.update_heartbeat()
        self.rtc.is_disconnected = True
        
    def on_heartbeat(self):
        """
        Method gets called when socket-io beats.
        """
        
        _log.debug('SocketIO heartbeat')
        self.rtc.update_heartbeat()

    def on_activity_updated(self, *args):
        """
        Method gets called when socket-io receives 'activity_updated' event.
        """
        
        _log.info('SocketIO received \'Activity Updated\' event')
        self.rtc.update_heartbeat()
        api.session.get_config()  #get the config as activities are updated

    def on_activitylist_in_category_updated(self, *args):
        """
        Method gets called when socket-io receives 'activitylist_in_category_updated' event.
        """
        
        _log.info('SocketIO received \'Activity List Updated\' event')
        self.rtc.update_heartbeat()
        api.session.get_config()  #get the config as activities are updated

    def on_agent_removed(self, *args):
        """
        Method gets called when socket-io receives 'agent_removed' event.
        """
        
        _log.info('SocketIO received \'Agent Removed\' event')
        self.rtc.update_heartbeat()
        
        try:
            #stop the agent if it is not found in the list of servers            
            if args[0].get('servers'):
                self.univ.config.agent.get(['config', '_id']) in args[0]['servers'] and api.session.stop(api.Status.NOT_FOUND)
            else:
                api.session.stop(api.Status.NOT_FOUND)
        except:
            pass    

    def on_org_token_resetted(self, *args):
        """
        Method gets called when socket-io receives 'org_token_resetted' event.
        """
        
        _log.info('SocketIO received \'Organization Token Reset\' event')
        api.session.stop()  #stop the agent as the organization token was resetted.

    def on_server_category_changed(self, *args):
        """
        Method gets called when socket-io receives 'server_category_changed' event.
        """
        
        _log.info('SocketIO received \'Category Changed\' event')
        self.rtc.update_heartbeat()
        
        try:
            #get agent config if this is the agent changed category
            if args[0].get('servers'):
                self.univ.config.agent.get(['config', '_id']) in args[0]['servers'] and api.session.get_config()
            else:
                api.session.get_config()  #get the config as activities are updated
        except:
            pass

    def on_activity_deleted(self, *args):
        """
        Method gets called when socket-io receives 'activity_deleted' event.
        """
        
        _log.info('SocketIO received \'Activity Deleted\' event')
        self.rtc.update_heartbeat()
        
        try:
             #get agent config if this agent runs the activity that was deleted.
            args[0]['activity'] in self.univ.config.agent.get(['config', 'activities']) and api.session.get_config()
        except:
            pass
        
    def on_upgrade_agent(self, *args):
        """
        Method gets called when socket-io receives 'upgrade_agent' event.
        """
        
        _log.info('SocketIO received \'Upgrade Agent\' event')
        self.rtc.update_heartbeat()
        
        try:
            #match the version with the current version, and trigger an update_event
            args[0]['agentVersion'] != self.univ.config.agent.agentVersion and self.univ.event_dispatcher.trigger('update_agent')
        except:
            pass
        
    def on_logout(self, *args):
        """
        Method gets called when socket-io receives 'logout' event.
        """
        
        _log.info('SocketIO received \'Logout\' event')
        self.rtc.update_heartbeat()
        api.session.stop(api.Status.SESSION_CONFLICT)  #stop api as there is a session conflict.
        
    def on_env_variables_updated(self, *args):
        """
        Method gets called when socket-io receives 'env_variables_updated' event.
        """
        
        _log.info('SocketIO received \'Environment variables updated\' event')
        api.session.get_config()  #update the config in any case
        
    def on_metric_created(self, *args):
        """
        Method gets called when socket-io receives 'metric_created' event.
        """
        
        _log.info('SocketIO received \'Metric created\' event')
        api.session.get_config()  #update the config in any case
        
    def on_metric_updated(self, *args):
        """
        Method gets called when socket-io receives 'metric_updated' event.
        """
        
        _log.info('SocketIO received \'Metric updated\' event')
        api.session.get_config()  #update the config in any case
        
    def on_metric_deleted(self, *args):
        """
        Method gets called when socket-io receives 'metric_deleted' event.
        """
        
        _log.info('SocketIO received \'Metric deleted\' event')
        api.session.get_config()  #update the config in any case
        
class RTC(ThreadEx):    
    """
    Class implementing real time communication using socket-io.
    This runs socket-io wait in a seperate thread.
    """
    
    def __init__(self):
        """
        Constructor.
        """
        
        ThreadEx.__init__(self)  #initialize base class
        self.sio = None  #socket-io instance
        self.univ = universal.Universal()  #save the reference to Universal for optimized access
        self.is_stop = False  #flag tells whether to stop the thread.
        self.daemon = True  #run this thread as daemon as it should not block agent from shutting down
        self.is_disconnected = False  #whether socket-io is disconnected
        self.session_id = ''  #session id to verify handshake error
        self.update_heartbeat()  #set the heardbeat
        
    def on_response(self, response, *args, **kwargs):
        """
        This is a callback method to check whether the http response is a handshake error.
        Python implementation of Socket-io has a bug because of which it fails to identify this error.
        """
        
        if 'handshake error' in response.text:
            raise SocketIOHandShakeError('%d; %s' % (response.status_code, response.text))  #raise an exception so that socket-io wait can finish
               
    def connect(self):
        """
        Public method to connect socket-io
        """
        
        SocketIONamespace.rtc = self  #we need to access this object from socket-io namespace
        
        #keyword arguments for socket-io instance
        kwargs = {
            'Namespace': SocketIONamespace,  #socket-io namespace
            'cookies': api.session.cookies,  #cookies for authentication
            'hooks': {'response': self.on_response},  #hook for response
            'stream': True  #for long polling
        }
        
        #socket-io by default uses websocket transport, but websockets wont work behind a proxy
        #we force xhr polling in such cases
        if self.univ.details['isProxy'] == True:
            _log.info('Proxy detected; Forcing xhr-polling for SocketIO')
            kwargs['transports'] = ['xhr-polling']
        
        _log.debug('Waiting for SocketIO connection')
        exception = None
        
        try:
            #instantiate socket-io
            self.sio = None
            self.session_id = api.session.cookies.get('SessionID')
            self.sio = SocketIO(self.univ.get_url(), **kwargs)
        except SocketIOHandShakeError as e:  #handshake error
            exception = e
            _log.error('Failed to connect SocketIO; %s' % unicode(e))
        except Exception as e:
            exception = e
            _log.error(unicode(e))
        
        return exception
    
    def disconnect(self):
        """
        Method to disconnect socket-io
        """
        
        if self.sio != None:
            _log.debug('Disconnecting SocketIO')
            
            try:
                self.sio.disconnect()  #disconnect socket-io
            except:
                pass
            
            self.sio = None
    
    def stop(self):
        """
        Public method to stop RTC session thereby socket-io
        """
        
        self.is_stop = True  #set the stop flag
        self.disconnect()  #disconnect socket-io
            
    def update_heartbeat(self):
        """
        Public method to update socket-io heartbeat flag. 
        This is called whenever an activity happens in socket-io.
        """
        
        self.last_heartbeat = int(time.time())
        
    def is_heartbeating(self):
        """
        Public method to check whether socket-io is alive.
        Socket-io is considered alive if there was a heartbeat in last one hour.
        
        Returns:
            True if socket-io is alive else False
        """
        
        t = int(time.time())        
        is_beating = True if t - self.last_heartbeat < (60 * 60) else False
        return is_beating
    
    def wait_for_auth(self):
        """
        Method to check and perform auth
        The method returns imeediately if session ids missmatch or the stop event is set
        """
        
        #check whether we have a conflict in session ids, if so we can return immediately and connect again
        if self.session_id != api.session.cookies.get('SessionID') or self.is_stop or self.univ.stop_event.is_set():
            return
            
        #try to set auth status, if another thread has done it already we dont have to do anything
        #else we reset the post event and reauthenticate
        if api.session.auth_status(api.AuthStatus.UNAUTHORIZED):
            api.session.set_events(post_event = False)
            connection.Connection().reconnect()  #reauthenticate

        if self.univ.post_event.is_set() == False:
            _log.debug('%s waiting for post event' % self.name)
            self.univ.post_event.wait();  #wait for the auth to complete

    def exe(self):        
        """
        Method runs in a new thread
        """
        
        is_handshake_exception = True  #whether we have a handshake error
        
        while 1:  #continuous wait  
            is_handshake_exception and self.wait_for_auth()  #reauth on handshake error
        
            if self.is_stop == True or self.univ.stop_event.is_set():  #do we need to stop
                _log.debug('%s received stop event' % self.name)
                break
                
            exception = self.connect()  #try to connect
            
            if exception:  #redo in case of exception
                is_handshake_exception = isinstance(exception, SocketIOHandShakeError)
                continue
        
            try:
                self.sio.wait()  #wait and process socket-io events
            except SocketIOHandShakeError as e:  #a handshake error happens when authentication fails
                _log.error('Failed to connect SocketIO; %s' % unicode(e))
                is_handshake_exception = True  #mark as handshake error so that next iteration will perform auth
            except Exception as e:
                _log.error(unicode(e))
                is_handshake_exception = False
                self.disconnect()  #disconnect socket-io
                self.is_disconnected = True  #for any other exception we set the disconnect flag, so that we can call config again

def create_session():
    """
    Function to create an RTC session.
    
    Returns:
        RTC session.
    """
    
    global session
    session = RTC()
    return session