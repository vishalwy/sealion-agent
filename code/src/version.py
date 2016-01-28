"""
Version info
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys

MAJOR_VERSION = 4  #a major change is introduced
MINOR_VERSION = 0  #a minor change is introduced
UPDATE_VERSION = 0  #a bug fix for the last minor version
RELEASE_VERSION = 'n2'  #update this whenever a change need to be tested or released

#version string; do not update this directly!
__version__ = ('%d.%d.%d' + (RELEASE_VERSION and '.%s' or '%s')) % (MAJOR_VERSION, MINOR_VERSION, UPDATE_VERSION, RELEASE_VERSION)

    
def print_version():
    sys.stdout.write(__version__ + '\n')
    return True