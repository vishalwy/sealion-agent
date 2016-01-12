#!/usr/bin/env python

"""
Unregister agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import os
import sys

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
exe_path = os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0]
sys.path.insert(0, exe_path + '/src')
sys.path.insert(0, exe_path + '/lib')

import exit_status
import api

api.create_session()
api.session.ping()  #required to set the post event, as the post event is set only after auth
status = api.session.unregister()  #unregister the agent
sys.exit(exit_status.AGENT_ERR_SUCCESS if api.is_not_connected(status) == False else exit_status.AGENT_ERR_FAILED_CONNECT)

