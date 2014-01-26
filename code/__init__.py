#!/usr/bin/python
import sys
sys.path.append('lib')
sys.path.append('src')
sys.path.append('lib/websocket_client') 

import logging
logging.basicConfig(level = logging.DEBUG)

import services
services.start()

