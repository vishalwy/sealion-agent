#!/usr/bin/python

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os.path

exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]
sys.path.insert(0, exe_path + 'lib')

if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + 'lib/httplib')    
    
import requests

i, arg_len, write_out_code, f, url = 0, len(sys.argv), False, sys.stdout, ''
kwargs = {'stream': True, 'allow_redirects': False}
session = requests.Session()
method = session.get

try:
    while i < arg_len:
        if not i:
            i += 1
            continue

        arg = sys.argv[i]

        if arg[:1] == '-':
            if arg == '-x':
                i += 1
                kwargs['proxies'] = {}
                kwargs['proxies']['https'] = sys.argv[i]
                kwargs['proxies']['http'] = sys.argv[i]
            elif arg == '-H':
                i += 1
                kwargs['headers'] = kwargs['headers'] or {}
                iterator = iter([str.strip() for str in sys.argv[i].split(':')])
                kwargs['headers'].update(dict(zip(iterator, iterator)))
            elif arg == '-X':
                i += 1
                method = getattr(session, sys.argv[i].strip().lower())
            elif arg == '-d':
                i += 1
                kwargs['data'] = sys.argv[i]
            elif arg == '-w':
                i += 1
                if sys.argv[i].strip() == '%{http_code}':
                    write_out_code = True
            elif arg == '-o':
                i += 1
                f = open(sys.argv[i], 'wb')
            elif arg == '-L':
                kwargs['allow_redirects'] = True
        else:
            url = arg

        i += 1
except IndexError:
    sys.stderr.write('Error: ' + sys.argv[i - 1] + 'requires an argument')
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + str(e))
    sys.exit(1)
                
response = method(url, **kwargs)  

for chunk in response.iter_content(chunk_size = 1024):
    if chunk:
        f.write(chunk)
        f.flush()
        
f != sys.stdout and f.close()
write_out_code and sys.stdout.write('%d' % response.status_code)