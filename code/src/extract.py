import sys
import json
import signal
import re
import imp

class TimeoutException(BaseException):
    pass

class CustomException(BaseException):
    pass

def write_output(line, stream = sys.stdout):
    stream.write(line + '\n')
    stream.flush()

def extract_metrics(output, metrics, timeout = 0):
    context, ret = {'__builtins__': globals()['__builtins__']}, {}
    valid_types = ['int', 'float']

    for metric_id in metrics:
        timeout > 0 and signal.alarm(timeout)
        
        try:
            context['command_output'] = output
            context['metric_value'] = None
            parser = re.sub('(\\bTimeoutException\\b)|(\\bException\\b)', 'CustomException', metrics[metric_id]['parser'])
            parser = re.sub('\\bexcept\\s*:', 'except CustomException:', parser)
            exec(parser, context)
            value = context.get('metric_value')

            if type(value).__name__ not in valid_types:
                raise Exception('value should be %s' % ' or '.join(valid_types))

            if metrics[metric_id]['cumulative']:
                ret[metric_id] = value - Worker.metrics.get(metric_id, value)
                Worker.metrics[metric_id] = value
            else:
                ret[metric_id] = value
                
            write_output('debug: Exetracted value %s for metric %s' % (value, metric_id))
        except TimeoutException as e:
            write_output('Failed to extract metric %s; %s' % (metric_id, unicode(e)))
        except:
            write_output('Failed to extract metric %s; %s' % (metric_id, unicode(sys.exc_info()[1])))
        
        timeout > 0 and signal.alarm(0)
        
    return ret

def signal_handler(*args):
    raise TimeoutException('execution timedout')
    
if __name__ == '__main__':
    try:
        timeout = int(sys.argv[1])
    except:
        timeout = 0

    signal.signal(signal.SIGALRM, signal_handler)
    sys.modules['signal'] = imp.new_module('signal')
    
    try:
        while 1:
            data = json.loads(sys.stdin.readline())
            data = extract_metrics(data.get('output', ''), data.get('metrics', {}), timeout)
            write_output('data: %s' % json.dumps(data))
    except:
        pass
