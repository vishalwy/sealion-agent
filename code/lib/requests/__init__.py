"""
Wrapper module for requests https://pypi.python.org/pypi/requests
This module exports all the defenitions from the original requests module.
It also setsup the httplib module and disables urllib3 warnings
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os

def setup_requests():
    """
    Function to setup import path for the httplib used by requests and the original requests itself.
    This function is created only not to pollute the module namespace
    """
    
    #to avoid the bug reported at http://bugs.python.org/issue13684 we use a stable httplib version available with CPython 2.7.3 and 3.2.3
    #since httplib has been renamed to http, we have to add that also in the path so that import can find it
    curr_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, curr_path)
    sys.version_info[0] == 3 and sys.path.insert(0, curr_path + '/httplib')
    
#setup and import requests
setup_requests()
from request import *

#disable urllib3 warnings. https://github.com/kennethreitz/requests/issues/2495
packages.urllib3.disable_warnings() 