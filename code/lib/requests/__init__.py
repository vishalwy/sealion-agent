"""
Wrapper module for requests https://pypi.python.org/pypi/requests
This module exports all the defenitions from the original requests module.
It also setsup the httplib module, monkey patch SSL verification and disables urllib3 warnings
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os

def setup_requests():
    """
    Function to setup import path for the httplib used by requests and the original requests itself.
    """
    
    #to avoid the bug reported at http://bugs.python.org/issue13684 we use a stable httplib version available with CPython 2.7.3 and 3.2.3
    #since httplib has been renamed to http, we have to add that also in the path so that import can find it
    curr_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, curr_path)
    sys.version_info[0] == 3 and sys.path.insert(0, curr_path + '/httplib')
    
def apply_insecure_patch(orig_session, orig_get):
    """
    Function to patch requests.Session and requests.get so that SSL verification is disabled
    
    Args:
        orig_session: original requests.Session class; used in API module
        orig_get: original requests.get function; used by SocketIO module
        
    Returns:
        Tuple containing insecure version of requests.Session and requests.get
    """
    
    class InsecureSession(orig_session):
        """
        Private class inheriting from requests.Session 
        """
        
        def __init__(self):
            """
            Constructor to patch SSL verification default
            """
            
            orig_session.__init__(self)  #initialize with original constructor
            self.verify = False  #turn off SSL verification

    def insecure_get(*args, **kwargs):
        """
        Private function to patch requests.get
        
        Returns
            Return value from requests.get
        """
        
        kwargs['verify'] = False  #disable SSL verification
        return orig_get(*args, **kwargs)  #call the original target

    return InsecureSession, insecure_get
    
#setup and import requests
setup_requests()
from request import *

#whether to disable SSL verification? read it from main module
if getattr(sys.modules['__main__'], '__insecure_ssl__', False):
    Session, get = apply_insecure_patch(Session, get)

#disable urllib3 warnings. https://github.com/kennethreitz/requests/issues/2495
packages.urllib3.disable_warnings() 
