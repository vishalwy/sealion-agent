"""
Plugin to collect Linux system metrics.
This module should have get_data function that returns the data.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import re
import multiprocessing
import time

#Python 2.x vs 3.x
try:
    unicode = unicode
except:
    def unicode(object, *args, **kwargs):
        return str(object)
    
_log = logging.getLogger(__name__)  #module level logging

def get_data(metrics):
    """
    Function to get the data this module provides.
    
    Args:
        metrics: dict containing the metrics to extract
    
    Returns:
        dict containing data.
    """
    
    data = {
        'loadAvg1Min': 0,  #load average 1 min
        'loadAvg5Min': 0,  #load average 5 min
        'loadAvg15Min': 0,  #load average 15 min
        'cpuUsage': [],  #usage distribution for each cpu
        'memUsage': {},  #memory usage 
        'networkReads': [],  #network reads per second for each interface
        'networkWrites': [],  #network writes per second for each interface
        'diskReads': [],  #disk reads per second for each disk
        'diskWrites': []  #disk writes per second for each disk
    }
    
    #metrics that doesnt need sampling
    data['loadAvg1Min'], data['loadAvg5Min'], data['loadAvg15Min'] = get_load_avg()  #get load avg
    data['memUsage'].update(get_mem_usage())  #memory usage
    
    #metrics that needs sampling
    #they are written as a generator so that we can sleep before collection again
    generators = {
        'CPU usage': {
            'source': get_cpu_usage(),  #generator for cpu usage
            'data': {}
        },
        'network R/W': {
            'source': get_net_rw(),  #generator for network read write
            'data': {}
        },
        'disk R/W': {
            'source': get_disk_rw(),  #generator for disk read write
            'data': {}
        }
    }
    
    while 1:
        temp_data, active_gen_count = True, 0
    
        for key in generators:        
            try:
                generators[key]['data'] = next(generators[key]['source'])  #get the next value
                
                #this variable is to identify the presence of a generator that is yet to produce the valid data
                if temp_data:
                    temp_data = generators[key]['data']
                    
                active_gen_count += 1
            except (StopIteration, GeneratorExit):
                pass
            except Exception as e:
                _log.error('Failed to sample %s; %s' % (key, unicode(e)))
                
        #if all the generators are exhausted
        if active_gen_count == 0:
            break
            
        #yield the sampling duration so that caller can sleep and resume
        #we should yield only if there is atleast one generator which has not produced any data
        if not temp_data:
            yield 10  
    
    #append cpu usage for each cpu core
    for cpu, usage in generators['CPU usage']['data'].items():
        data['cpuUsage'].append({'name': cpu, 'value': usage})
        
    #append network read and write for each interface
    for interface, rw in generators['network R/W']['data'].items():
        data['networkReads'].append({'name': interface, 'value': rw['reads']})
        data['networkWrites'].append({'name': interface, 'value': rw['writes']})        
        
    #append disk read and write for each logical disk
    for device, rw in generators['disk R/W']['data'].items():
        data['diskReads'].append({'name': device, 'value': rw['reads']})
        data['diskWrites'].append({'name': device, 'value': rw['writes']})
        
    generators = None  #remove the reference to generators so that it can GCed
    
    yield {
        'output': data,
        'metrics': extract_metrics(data, metrics)
    }
    
def extract_metrics(data, metrics):
    """
    Function to extract the metrics from the data collected
    
    Args:
        data: the data from which the metrics to be extracted
        metrics: dict representing the metrics
        
    Returns:
        dict containing the metrics 
    """
    
    ret = {}
    
    #loop through the metrics and extract metrics
    for metric in metrics:
        try:
            id, parser = metric, metrics[metric]['parser']

            if parser == 'get_loadAvg1Min':
                ret[id] = data['loadAvg1Min']
            elif parser == 'get_loadAvg5Min':
                ret[id] = data['loadAvg5Min']
            elif parser == 'get_loadAvg15Min':
                ret[id] = data['loadAvg15Min']
            elif parser == 'get_cpuUsage':
                values = [sum([temp['value'][key] for key in ['us', 'ni', 'sy', 'hi', 'si']]) for temp in data['cpuUsage']]
                ret[id] = float('%.2f' % (float(sum(values)) / len(values))) 
            elif parser == 'get_memUsage':
                ret[id] = float('%.2f' % ((float(data['memUsage']['res'] - data['memUsage']['cached']) / data['memUsage']['total']) * 100))
            elif parser == 'get_networkReads':
                values = [temp['value'] for temp in data['networkReads']]
                ret[id] = float('%.2f' % (float(max(values)) / len(values))) 
            elif parser == 'get_networkWrites':
                values = [temp['value'] for temp in data['networkWrites']]
                ret[id] = float('%.2f' % (float(max(values)) / len(values))) 
            elif parser == 'get_diskReads':
                values = [temp['value'] for temp in data['diskReads']]
                ret[id] = float('%.2f' % (float(max(values)) / len(values))) 
            elif parser == 'get_diskWrites':
                values = [temp['value'] for temp in data['diskWrites']]
                ret[id] = float('%.2f' % (float(max(values)) / len(values))) 
        except Exception as e:
            _log.error('Failed to extract metric %s; %s' % (id, unicode(e)))
            
    return ret

def get_load_avg():
    """
    Function to get load avg.
    
    Returns:
        [loadAvg1Min, loadAvg5Min, loadAvg15Min]
    """
    
    with open('/proc/loadavg') as f:
        line = f.readline()
    
    return [float(x) for x in line.split()[:3]]

def get_mem_usage():
    """
    Function to get memory usage.
    
    Returns:
        dict containing memory usage stats
    """
    
    mem_total, mem_free, vm_total, mem_cached = 0, 0, 0, 0
    
    with open('/proc/meminfo') as f:
        for line in f:
            if line.startswith('MemTotal:'):
                mem_total = int(line.split()[1])
            elif line.startswith('MemFree:'):
                mem_free = int(line.split()[1])
            elif line.startswith('VmallocTotal:'):
                vm_total = int(line.split()[1])
            elif line.startswith('Cached:'):
                mem_cached = int(line.split()[1])
                
    return {
        'total': mem_total,
        'res': mem_total - mem_free,
        'virt': vm_total,
        'cached': mem_cached
    }

def get_cpu_usage():
    """
    Generator to get the cpu usage in percentage for the sampling duration given.
        
    Yields:
        dict containing cpu usage percents for each cpu
    """
    
    keys = ['us', 'ni', 'sy', 'id', 'wa', 'hi', 'si', 'st']  #usage % to be returned
    
    with open('/proc/stat') as f1:
        with open('/proc/stat') as f2:
            content1 = f1.read()  #first collection
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            
    cpu_count = multiprocessing.cpu_count()  #total number of cpu cores available
    lines1, lines2 = content1.splitlines(), content2.splitlines()
    data, deltas = {}, {}
    
    #if only one cpu available, read only the first line, else read total cpu count lines starting from the second line
    i, cpu_count = (1, cpu_count + 1) if cpu_count > 1 else (0, 1)
    
    #extract deltas
    while i < cpu_count:
        line_split1 = lines1[i].split()
        line_split2 = lines2[i].split()
        deltas[line_split1[0]] = [int(b) - int(a) for a, b in zip(line_split1[1:], line_split2[1:])]
        i += 1
    
    for key in deltas:
        #calculate the percentage
        total = sum(deltas[key]) or 1
        data[key] = dict(zip(keys, [100 - (100 * (float(total - x) / total)) for x in deltas[key]]))
    
    yield data

def get_net_rw():
    """
    Generator to get network reads and writes for the duration given.
    
    Yields:
        dict containing network read and writes for each interface.
    """
        
    with open('/proc/net/dev') as f1:
        with open('/proc/net/dev') as f2:
            content1 = f1.read()  #first collection
            sample_time = time.time()
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            sample_time = time.time() - sample_time  #calculate the sampling time took
            
    #network interfaces
    interfaces = [interface[:-1].strip() for interface in re.findall('^\s*.+:', content1, flags = re.MULTILINE)]
            
    #initialize the dict with interfaces and values
    data = dict(zip(interfaces, [dict(zip(['reads', 'writes'], [0, 0])) for interface in interfaces]))
            
    for line in content1.splitlines():  #read through first collection
        for interface in [interface_x for interface_x in interfaces if '%s:' % interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = int(fields[0])
            data[interface]['writes'] = int(fields[8])
            break
    
    for line in content2.splitlines():  #read through second collection
        for interface in [interface_x for interface_x in interfaces if '%s:' % interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = int((int(fields[0]) - data[interface]['reads']) / sample_time)
            data[interface]['writes'] = int((int(fields[8]) - data[interface]['writes']) / sample_time)
            break
    
    yield data

def get_disk_rw():
    """
    Generator to get disk reads and writes for the duration given.
    
    Yields:
        dict containing disk reads and writes for each device.
    """
    
    #get te list of devices
    with open('/proc/partitions') as f:
        devices = [re.search('\s([^\s]+)$', line).group(1).strip() for line in re.findall('^\s*[0-9]+\s+[0-9]+\s+[0-9]+\s+.+$', f.read(), flags = re.MULTILINE)]
    
    with open('/proc/diskstats') as f1:
        with open('/proc/diskstats') as f2:
            content1 = f1.read()  #first collection
            sample_time = time.time()
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            sample_time = time.time() - sample_time  #calculate the sampling time took
            
    #initialize the dict with interfaces and values
    data = dict(zip(devices, [dict(zip(['reads', 'writes'], [0, 0])) for device in devices]))

    for line in content1.splitlines():  #read through first collection
        for device in [device_x for device_x in devices if '%s ' % device_x in line]:
            fields = line.strip().split('%s ' % device)[1].split()
            data[device]['reads'] = int(fields[0])
            data[device]['writes'] = int(fields[4])
            break
    
    for line in content2.splitlines():  #read through second collection
        for device in [device_x for device_x in devices if '%s ' % device_x in line]:
            fields = line.strip().split('%s ' % device)[1].split()
            data[device]['reads'] = int((int(fields[0]) - data[device]['reads']) / sample_time)
            data[device]['writes'] = int((int(fields[4]) - data[device]['writes']) / sample_time)
            break            
            
    yield data