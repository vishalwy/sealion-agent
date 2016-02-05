import sys
import json
import signal
import re
import imp

class TimeoutException(BaseException):
    pass

def write_output(line, stream = sys.stdout):
    stream.write(line + '\n')
    stream.flush()

def extract_metrics(output, metrics, job, timeout = 0):
    context, ret = {'__builtins__': globals()['__builtins__']}, {}
    valid_types = ['int', 'float']

    for metric_id in metrics:
        timeout > 0 and signal.alarm(timeout)
        
        try:
            context['command_output'] = output
            context['metric_value'] = None
            exec(re.sub('\\bexcept\\s*:', 'except Exception:', metrics[metric_id]['parser']), context)
            value = context.get('metric_value')

            if type(value).__name__ not in valid_types:
                raise Exception('value should be %s' % ' or '.join(valid_types))

            if metrics[metric_id]['cumulative']:
                ret[metric_id] = value - Worker.metrics.get(metric_id, value)
                Worker.metrics[metric_id] = value
            else:
                ret[metric_id] = value
                
            write_output('debug: Extracted value %s for metric %s from %s' % (value, metric_id, job))
        except:
            write_output('Failed to extract metric %s from %s; %s' % (metric_id, job, unicode(sys.exc_info()[1])))
        
        timeout > 0 and signal.alarm(0)
        
    return ret

def signal_handler(*args):
    raise TimeoutException('execution timedout')
    
if __name__ == '__main__':
    try:
        timeout = int(sys.argv[1])
        
        if timeout <= 0:
            raise Exception
    except:
        write_output('Missing or invalid timeout', sys.stderr)
        write_output('Usage: %s <execution timeout>' % sys.argv[0])
        exit(1)

    signal.signal(signal.SIGALRM, signal_handler)
    sys.modules['signal'] = imp.new_module('signal')
    
    try:
        while 1:
            data = json.loads(sys.stdin.readline())
            data = extract_metrics(data['output'], data['metrics'], data['job'], timeout)
            write_output('data: %s' % json.dumps(data))
    except:
        pass
