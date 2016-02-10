"""
Module to extract the metrics from the output given.
This is not an attempt to sandbox python code, rather an attempt to interrupt the metric evaluation that runs, say infinitely due to a logical error in the parser used.
When run as main script, it reads from stdin and write the result to stdout. 
The parser code will not be able to use signal module as it is modified for the executing context. This is required to prevent the code from installing signal handlers or sending signals.
Also the parser code cannot have generic exception or BaseException handlers, as it will be modified to become Exception handlers
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import sys
import json
import signal
import re
import imp
import os.path

#when script is run as main script, path to custom modules will be missing
#in this case we need to import constructs which is located in lib directory
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)).rsplit('/', 1)[0] + '/lib')
    
from constructs import unicode  
timeout, cumulative_metrics = 0, {}

class TimeoutException(BaseException):
    """
    Exception used to interrupt the parser after the timeout given
    """
    pass

def write_output(line, stream = sys.stdout):
    """
    Function to write the output to the stream given. Use this to flush the output after every write
    
    Args:
        line: the line to be written, a new line will be appended to the line
        stream: the file handle to write to
    """
    
    stream.write(line + '\n')
    stream.flush()
    
def sanitize_parser(code):
    """
    Function to sanitize the parser code
    This replaces generic exception or BaseException handler to Exception handler
    
    Args:
        code: parser code to sanitize
        
    Returns:
        Sanitized code
    """
    
    exception_pattern = re.compile('(\\s*except)((\\s*)|(((\\s*\\(\\b[^\\b]+\\b\)\\s*)|(\\s+\\b[^\\s,]+\\b\\s*))((as|,)\\s*[^\\s]+\\s*)?))(:)')
    
    def replace_exception(match):
        """
        Helper function to replace exception handlers
        
        Args:
            match: the match object
            
        Returns:
            Replacement string
        """
        
        if match.group(3) != None:  #if we have a generic exception handler
            group_2 = ' Exception'
        else:  #if we have exception BaseException handler
            group_5, group_8 = match.group(6) or match.group(7), match.group(8)
            group_2 = '' if not group_5 else re.sub('\\bBaseException\\b', 'Exception', group_5 ) + (group_8 if group_8 else '')
        
        return match.group(0) if not group_2 else '%s%s%s' % (match.group(1), group_2, match.group(10))
    
    return re.sub(exception_pattern, replace_exception, code)

def extract_metrics(output, metrics, job):
    """
    Function to extract the metrics from the output given
    
    Args:
        output: command output to be parsed
        metrics: the metrics to be extracted
        job: name of the job for which the output is produced, for logging purpose
        
    Returns:
        dict representing the metrics extracted
    """
    
    context, ret = {'__builtins__': globals()['__builtins__']}, {}
    valid_types = ['int', 'float']  #valid types for the value extracted
    
    for metric_id in metrics:
        #set the alarm to signal after the mentioned timeout which in turn raises an exception
        timeout > 0 and signal.alarm(timeout)  
        
        try:
            #set the context 
            context['command_output'] = output
            context['metric_value'] = None
            
            #execute the code in the context created
            exec(metrics[metric_id]['parser'], context)
            
            #get the value
            value = context.get('metric_value')

            #raise the exception if it is not a valid type
            if type(value).__name__ not in valid_types:
                raise Exception('value should be %s' % ' or '.join(valid_types))

            #set the value based on the cumulative nature of the metric
            if metrics[metric_id]['cumulative']:
                ret[metric_id] = value - cumulative_metrics.get(metric_id, value)
                cumulative_metrics[metric_id] = value
            else:
                ret[metric_id] = value
                
            write_output('debug: Extracted value %s for metric %s from %s' % (value, metric_id, job))
        except:
            write_output('Failed to extract metric %s from %s; %s' % (metric_id, job, unicode(sys.exc_info()[1])))
        
        timeout > 0 and signal.alarm(0)  #reset the alarm
        
    return ret

def signal_handler(*args):
    """
    Function to handle SIGALRM
    """
    
    #raise the exception so that parser code evaluation can be interrupted
    raise TimeoutException('execution timedout')
    
if __name__ == '__main__':  #if this is the main module
    try:
        timeout = int(sys.argv[1])
        
        if timeout <= 0:  #there should be a integer timeout > 0
            raise Exception
    except:
        write_output('Missing or invalid timeout', sys.stderr)
        write_output('Usage: %s <execution timeout>' % sys.argv[0])
        exit(1)

    signal.signal(signal.SIGALRM, signal_handler)  #install the signal handler  for alarm 
    
    #replace the signal module with an empty module so that parser code cannot use them
    #if we let them use they can bypass the architecture by installing a new signal handler or generating signals
    sys.modules['signal'] = imp.new_module('signal') 
    
    try:
        while 1:  #continuous read
            data = json.loads(sys.stdin.readline())  #data should be in json format
            data = extract_metrics(data['output'], data['metrics'], data['job'])  #sxtract metrics
            write_output('data: %s' % json.dumps(data))
    except:
        pass
