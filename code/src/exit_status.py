"""
Exit codes for the agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

AGENT_ERR_SUCCESS = 0
AGENT_ERR_FAILED_DAEMONIZE_1 = 20
AGENT_ERR_FAILED_DAEMONIZE_2 = 21
AGENT_ERR_FAILED_PID_FILE = 22
AGENT_ERR_FAILED_OPEN_LOG = 23
AGENT_ERR_FAILED_INITIALIZE = 24
AGENT_ERR_FAILED_CONNECT = 25
AGENT_ERR_ALREADY_RUNNING = 26
AGENT_ERR_FAILED_FIND_USER = 27
AGENT_ERR_FAILED_CHANGE_GROUP_OR_USER = 28
AGENT_ERR_FAILED_TERMINATE = 29
AGENT_ERR_RESTART = 30
AGENT_ERR_FAILED_REGISTER = 31
AGENT_ERR_NOT_RESPONDING = 32
AGENT_ERR_CRASHED = 33