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
exe_path = os.path.dirname(os.path.realpath(__file__))
exe_path = exe_path[:-1] if exe_path != '/' and exe_path[-1] == '/' else exe_path
exe_path = exe_path[:exe_path.rfind('/')]

#add module lookup paths to sys.path so that import can find them
#we are inserting at the begining of sys.path so that we can be sure that we are importing the right module
sys.path.insert(0, exe_path + '/src')
sys.path.insert(0, exe_path + '/lib')

#to avoid the bug reported at http://bugs.python.org/issue13684 we use a stable httplib version available with CPython 2.7.3 and 3.2.3
#since httplib has been renamed to http, we have to add that also in the path so that import can find it
if sys.version_info[0] == 3:
    sys.path.insert(0, exe_path + '/lib/httplib')    
    
import requests
from constructs import unicode

def usage(is_help = False):
    """
    Function to show usage information
    
    Args:
        is_help: Whether to show the full help or just the command to show help
        
    Returns:
        True
    """
    
    if is_help == False:
        sys.stdout.write('Run \'%s --help\' for more information\n' % sys.argv[0])
        return True
        
    usage_info = 'Usage: %s [options] <URL1>, ...\nOptions:\n' % sys.argv[0]
    usage_info += ' -x,  --proxy <arg>       Proxy server details\n'
    usage_info += ' -X,  --request <arg>     Request method to be used; %s\n' % '|'.join(methods)
    usage_info += ' -H,  --header <arg>      Custom header to be sent to the server; it should be in the form \'header:value\'\n'
    usage_info += ' -d,  --data <arg>        Data for the request\n'
    usage_info += ' -w,  --write-out <arg>   What to output after request completes; only variable supported is %{http_code}\n'
    usage_info += ' -o,  --output <arg>      Write outpt to file instead of stdout\n'
    usage_info += ' -L,  --location          Follow redirects; OFF by default\n'
    usage_info += ' -k,  --insecure          Allow connections to SSL sites without certificates\n'
    usage_info += ' -s,  --silent            Does nothing; kept only for compatability with curl command\n'
    usage_info += ' -h,  --help              Display this information\n'
    sys.stdout.write(usage_info)
    return True

output_format, output_file, urls, f = '', '', [], None

#keyword arguments for requests
kwargs = {
    'stream': True,  #to retreive content chunk wise
    'allow_redirects': False  #follow redirects
}

session = requests.Session()  #create the request session to use
method = session.get  #default request method
methods = ['post', 'get', 'put', 'delete', 'patch', 'options']  #available http methods

def convert_special(data):
    """
    Function to convert specail charecters.
    
    Args:
        data: string to be converted.
        
    Returns:
        converted string
    """
    
    try:
        return data.encode('utf-8').decode('unicode-escape').replace('%%', '%')
    except:
        return data.encode('utf-8').decode('string-escape').replace('%%', '%')

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
    long_options = ['proxy=', 'request=', 'header=', 'data=', 'write-out=', 'output=', 'location', 'insecure', 'silent', 'help']
    options, args = getopt.getopt(sys.argv[1:], 'x:H:X:d:w:o:Lksh', long_options)
    
    for option, arg in options:
        if option in ['-x', '--proxy']:  #proxy
            kwargs['proxies'] = {'https': arg, 'http': arg}  #set proxy for both http and https. depending on the url scheme it will use the right one
        elif option in ['-H', '--header']:  #headers
            #update the headers. header will be in the form "header:value"
            kwargs['headers'] = kwargs.get('headers', {})
            iterator = iter([str.strip() for str in arg.split(':', 1)])
            kwargs['headers'].update(dict(zip(iterator, iterator)))
        elif option in ['-X', '--request']:  #http method to use
            if arg.lower() in methods:
                method = getattr(session, arg.lower())  #get the session method currusponding to the value
            else:
                sys.stderr.write('Uknown argument \'%s\' for %s\n' % (arg, option))  #unknown method
                usage() and sys.exit(1)
        elif option in ['-d', '--data']:  #data to be send
            kwargs['data'] = arg  #set the data
        elif option in ['-w', '--write-out']:  #what to write to stdout after completion
            output_format = arg
        elif option in ['-o', '--output']:  #output file
            output_file = arg
        elif option in ['-L', '--location']:  #allow url redirection
            kwargs['allow_redirects'] = True
        elif option in ['-k', '--insecure']:  #allow url redirection
            kwargs['verify'] = False
        elif option in ['-h', '--help']:
            usage(True) and sys.exit(0)
            
    #all the non option arguments are considered the urls to fetch
    for arg in args: 
        url = arg.strip()
        
        #default to http scheme if no scheme specified an then add to list of urls
        url and urls.append(url if re.match('https?://.*', url) else 'http://' + url)
except getopt.GetoptError as e:
    sys.stderr.write(unicode(e).capitalize() + '\n')  #missing option value
    usage() and sys.exit(1)
except Exception as e:
    sys.stderr.write('Error: ' + unicode(e) + '\n')
    sys.exit(1)
    
if not urls:  #no urls specified
    sys.stderr.write('Please specify atleast one URL\n')
    usage() and sys.exit(1)
                    
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
