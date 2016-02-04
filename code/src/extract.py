import sys
import json
import signal
import re
import imp

class TimeoutException:
    pass

def extract_metrics(output, metrics, timeout = 0):
    context, ret = {'__builtins__': globals()['__builtins__']}, {}
    valid_types = ['int', 'float']

    for metric in metrics:
        timeout > 0 and signal.alarm(timeout)
        
        try:
            context['command_output'] = output
            context['metric_value'] = None
            metric_id = metric
            metric, parser = metrics[metric_id], metric['parser']
            parser = re.sub('\\bTimeoutException\\b', 'Exception', parser)
            parser = re.sub('\\bexcept\\s*:', 'except Exception:', parser)
            exec(parser, context)
            value = context.get('metric_value')

            if type(value).__name__ not in valid_types:
                raise Exception('value should be %s' % ' or '.join(valid_types))

            if metric['cumulative']:
                ret[metric_id] = value - Worker.metrics.get(metric_id, value)
                Worker.metrics[metric_id] = value
            else:
                ret[metric_id] = value
        except TimeoutException:
            pass
        except:
            pass
        
        timeout > 0 and signal.alarm(0)
        
    return ret

def signal_handler(*args):
    raise TimeoutException
    
if __name__ == '__main__':
    try:
        timeout = int(sys.argv[1])
    except:
        timeout = 0

    signal.signal(signal.SIGALRM, signal_handler)
    sys.modules['signal'] = imp.new_module('signal')
    
    while 1:
        data = json.loads(sys.stdin.readline().decode('utf-8', 'replace').rstrip())
        data = extract_metrics(data.get('output', ''), data.get('metrics', {}), timeout)
        sys.stdout.write((json.dumps(data) + '\n').encode('utf-8'))
    
    