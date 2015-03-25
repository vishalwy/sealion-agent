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
import getopt

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

output_format, output_file, urls, f = '', '', [], None
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
    options, args = getopt.getopt(sys.argv[1:], 'x:H:X:d:w:o:Lh')
    
    for option, arg in options:
        if option == '-x':  #proxy
            kwargs['proxies'] = {'https': arg, 'http': arg}  #set proxy for both http and https. depending on the url scheme it will use the right one
        elif option == '-H':  #headers
            #update the headers. header will be in the form "header:value"
            kwargs['headers'] = kwargs.get('headers', {})
            iterator = iter([str.strip() for str in arg.split(':')])
            kwargs['headers'].update(dict(zip(iterator, iterator)))
        elif option == '-X':  #http method to use
            if arg.lower() in ['post', 'get', 'put', 'delete', 'patch', 'options']:
                method = getattr(session, arg.lower())  #get the session method currusponding to the value
            else:
                raise Exception('unknown http method \'%s\'' % arg.lower())
        elif option == '-d':  #data to be send
            kwargs['data'] = arg  #set the data
        elif option == '-w':  #what to write to stdout after completion
            output_format = arg
        elif option == '-o':  #output file
            output_file = arg
        elif option == '-L':  #allow url redirection
            kwargs['allow_redirects'] = True
        elif option == '-h':
            sys.stdout.write(usage)
            sys.exit(0)
            
    #all the non option arguments are considered the urls to fetch
    for arg in args: 
        url = arg.strip()
        
        #default to http scheme if no scheme specified an then add to list of urls
        url and urls.append(url if re.match('https?://.*', url) else 'http://' + url)
except getopt.GetoptError as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n' + usage)  #missing option value
    sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
if not urls:  #no urls specified
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
