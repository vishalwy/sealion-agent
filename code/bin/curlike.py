#!/usr/bin/env python

"""
Provides curl like functionality. 
The script is provided to upgrade agent where curl is not available.
It provides the minimum functionality curl-install.sh requires to download and install the agent.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import os.path
import re

#get the exe path, which is the absolute path to the parent directory of the module's direcotry
exe_path = os.path.dirname(os.path.abspath(__file__))
exe_path = exe_path[:-1] if exe_path[len(exe_path) - 1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/') + 1]

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
sys.path.insert(0, exe_path + 'src')
sys.path.insert(0, exe_path + 'lib')

#to avoid the bug reported at http://bugs.python.org/issue13684 we use a stable httplib version available with CPython 2.7.3 and 3.2.3
#since httplib has been renamed to http, we have to add that also in the path so that import can find it
if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + 'lib/httplib')    
    
import requests
from constructs import unicode

i, arg_len, output_format, output_file, urls, f = 1, len(sys.argv), '', '', [], None
usage = 'Usage: curlike.py {[-x <proxy>] [-H <header>] [-X <http method>] [-d <data>] [-w <write out>] [-o <output file>] [-L <allow redirects>] URLs | -h for Help}\n'

#keyword arguments for requests
kwargs = {
    'stream': True,  #to retreive content chunk wise
    'allow_redirects': False  #follow redirects
}

session = requests.Session()
method = session.get  #default request method

def convert_special(data):
    """
    Function to convert specail charecters.
    
    Args:
        data: string to be converted.
        
    Returns:
        converted string
    """
    
    try:
        return data.encode('utf8').decode('unicode-escape').replace('%%', '%')
    except:
        return data.encode('utf8').decode('string-escape').replace('%%', '%')

def format_output(response):
    """
    Function to format the output when -w is specified.
    
    Args:
        response: response object for the request
        
    Returns:
        String where variables are substituted.
    """
    
    def eval_variable(match_obj):        
        ret = ''
        
        #replace the known variables
        if match_obj.group(0) == '%{http_code}':
            ret = '%d' % response.status_code
        
        return ret
    
    return re.sub('%{[a-zA-Z0-9_]+}', eval_variable, convert_special(output_format))

def exception_hook(*args, **kwargs):
    """
    Callback function for handling unhandled exception
    """
    
    if f != None and f != sys.stdout:
        f.close()
        os.remove(output_file)

sys.excepthook = exception_hook  #set the exception hook

try:
    while i < arg_len:  #read all the arguments
        arg = sys.argv[i]

        if arg[:1] == '-':  #considering single letter options only
            if arg == '-x':  #proxy
                i += 1  #read option value
                
                #set proxy for both http and https. depending on the url scheme it will use the right one
                kwargs['proxies'] = {}
                kwargs['proxies']['https'] = sys.argv[i]
                kwargs['proxies']['http'] = sys.argv[i]
            elif arg == '-H':  #headers
                i += 1  #read option value
                
                #update the headers. header will be in the form "header:value"
                kwargs['headers'] = kwargs.get('headers') or {}
                iterator = iter([str.strip() for str in sys.argv[i].split(':')])
                kwargs['headers'].update(dict(zip(iterator, iterator)))
            elif arg == '-X':  #http method to use
                i += 1  #read option value
                
                if sys.argv[i].strip().lower() in ['post', 'get', 'put', 'delete', 'patch', 'options']:
                    method = getattr(session, sys.argv[i].strip().lower())  #get the session method currusponding to the value
                else:
                    raise Exception('unknown http method \'%s\'' % sys.argv[i].strip().lower())
            elif arg == '-d':  #data to be send
                i += 1  #read option value
                kwargs['data'] = sys.argv[i]  #set the data
            elif arg == '-w':  #what to write to stdout after completion
                i += 1  #read option value
                output_format = sys.argv[i]
            elif arg == '-o':  #output file
                i += 1  #read option value
                output_file = sys.argv[i]
            elif arg == '-L':  #allow url redirection
                kwargs['allow_redirects'] = True
            elif arg == '-h':
                sys.stdout.write(usage)
                sys.exit(0)
        else:  #anything else is considered as url to fetch
            url = arg.strip()
            
            if url:
                url = url if re.match('https?://.*', url) else 'http://' + url  #default to http scheme if no scheme specified
                urls.append(url)

        i += 1  #next option
except IndexError:
    sys.stderr.write('Error: %s requires an argument\n%s' % (sys.argv[i - 1], usage))  #missing option value
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
if len(urls) == 0:  #no urls specified
    sys.stderr.write('Error: please specify atleast one URL\n%s' % usage)
    sys.exit(1)
                    
try:
    f = sys.stdout if not output_file else open(output_file, 'wb')  #if no output file is specified, write to stdout
    
    for url in urls:  #fetch all urls
        response = method(url, **kwargs)  

        #retreive data chunkwise and write it to file
        for chunk in response.iter_content(chunk_size = 1024):
            if chunk:
                try:
                    f.write(chunk)
                except:
                    f.buffer.write(chunk)
                    
                f.flush()

        sys.stdout.write(format_output(response))  #write out variable
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')    
    sys.exit(1)
    
f != None and f != sys.stdout and f.close()  #close output file
