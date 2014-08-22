"""
Plugin to collect Linux system metrics.
This module should have get_data function that returns the data.
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import re
import os
import multiprocessing
import time

def get_data():
    """
    Function to get the data this module provides.
    
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
    sampling_duration = 1
    cpu_usage_gen = get_cpu_usage(sampling_duration)  #generator for cpu usage
    net_rw_gen = get_net_rw(sampling_duration)  #generator for network read write
    disk_rw_gen = get_disk_rw(sampling_duration)  #generator for disk read write
        
    while 1:  #now start sampling, whenever we have walid data, we can exit the loop
        cpu_usage = next(cpu_usage_gen)
        net_rw = next(net_rw_gen)
        disk_rw = next(disk_rw_gen)
        
        if cpu_usage or net_rw or disk_rw:  #we have valid data
            break
        
        time.sleep(sampling_duration)
    
    #append cpu usage for each cpu core
    for cpu, usage in cpu_usage.items():
        data['cpuUsage'].append({'name': cpu, 'value': usage})
        
    #append network read and write for each interface
    for interface, rw in net_rw.items():
        data['networkReads'].append({'name': interface, 'value': rw['reads']})
        data['networkWrites'].append({'name': interface, 'value': rw['writes']})        
        
    #append disk read and write for each logical disk
    for device, rw in disk_rw.items():
        data['diskReads'].append({'name': device, 'value': rw['reads']})
        data['diskWrites'].append({'name': device, 'value': rw['writes']})
    
    return data

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

def get_cpu_usage(*args):
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
        total = sum(deltas[key])
        data[key] = dict(zip(keys, [100 - (100 * (float(total - x) / total)) for x in deltas[key]]))
    
    yield data

def get_net_rw(sampling_duration):
    """
    Generator to get network reads and writes for the duration given.
    
    Args:
        sampling_duration: time in seconds between the two collection.
    
    Yields:
        dict containing network read and writes for each interface.
    """
    
    interfaces = [file for file in os.listdir('/sys/class/net/') if file != 'lo']  #network interfaces
        
    with open('/proc/net/dev') as f1:
        with open('/proc/net/dev') as f2:
            content1 = f1.read()  #first collection
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            
    #initialize the dict with interfaces and values
    data = dict(zip(interfaces, [dict(zip(['reads', 'writes'], [0, 0])) for interface in interfaces]))
            
    for line in content1.splitlines():  #read through first collection
        for interface in [interface_x for interface_x in interfaces if '%s:' % interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = int(fields[1])
            data[interface]['writes'] = int(fields[9])
            break
    
    for line in content2.splitlines():  #read through second collection
        for interface in [interface_x for interface_x in interfaces if '%s:' % interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = (int(fields[1]) - data[interface]['reads']) / float(sampling_duration)
            data[interface]['writes'] = (int(fields[9]) - data[interface]['writes']) / float(sampling_duration)
            break
    
    yield data

def get_disk_rw(sampling_duration):
    """
    Generator to get disk reads and writes for the duration given.
    
    Args:
        sampling_duration: time in seconds between the two collection.
    
    Yields:
        dict containing disk reads and writes for each device.
    """
    
    #get te list of devices
    with open('/proc/partitions') as f:
        devices = [re.search('\s([^\s]+)$', line).group(1).strip() for line in re.findall('^\s*[0-9]+\s+[1-9]+.*$', f.read(), flags = re.MULTILINE)]
    
    with open('/proc/diskstats') as f1:
        with open('/proc/diskstats') as f2:
            content1 = f1.read()  #first collection
            yield {}  #yield so that caller can put delay before sampling again
            content2 = f2.read()  #second collection
            
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
            data[device]['reads'] = (int(fields[0]) - data[device]['reads']) / float(sampling_duration)
            data[device]['writes'] = (int(fields[4]) - data[device]['writes']) / float(sampling_duration)
            break            
            
    yield data
