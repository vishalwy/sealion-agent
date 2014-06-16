"""
Plugin to collect Linux system metrics.
This module should have get_data function that returns the data.
"""

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
    
    data['loadAvg1Min'], data['loadAvg5Min'], data['loadAvg15Min'] = get_load_avg()  #get load avg
    
    #get the cpu usage for each cpu found
    for cpu, usage in get_cpu_usage().items():
        data['cpuUsage'].append({'name': cpu, 'value': usage})
        
    data['memUsage'].update(get_mem_usage())  #memory usage
    
    #find network read and write for each interface
    for interface, rw in get_net_rw([file for file in os.listdir('/sys/class/net/') if file != 'lo']).items():
        data['networkReads'].append({'name': interface, 'value': rw['reads']})
        data['networkWrites'].append({'name': interface, 'value': rw['writes']})
        
        
    for interface, rw in get_net_rw([file for file in os.listdir('/sys/class/net/') if file != 'lo']).items():
        data['networkReads'].append({'name': interface, 'value': rw['reads']})
        data['networkWrites'].append({'name': interface, 'value': rw['writes']})
        
        
    #find disk read and write for each logical disk
    with open('/proc/partitions') as f:
        devices = [re.search('\s([^\s]+)$', line).group(1).strip() for line in re.findall('^\s*[0-9]+\s+[1-9]+.*$', f.read(), flags = re.MULTILINE)]
        
        for device, rw in get_disk_rw(devices).items():
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

def get_cpu_usage(sampling_duration = 1):
    """
    Function to get the cpu usage in percentage for the sampling duration given.
    
    Args:
        sampling_duration: time in seconds between the two collection.
        
    Returns:
        A dict containing cpu usage percents for each cpu
    """
    
    keys = ['us', 'ni', 'sy', 'id', 'wa', 'hi', 'si', 'st']  #usage % to be returned
    deltas = get_cpu_usage_deltas(sampling_duration)  #get the usage deltas
    ret = {}
    
    for key in deltas:
        #calculate the percentage
        total = sum(deltas[key])
        ret[key] = dict(zip(keys, [100 - (100 * (float(total - x) / total)) for x in deltas[key]]))
        
        #delete additional keys
        del ret[key]['hi']
        del ret[key]['si']
    
    return  ret

def get_cpu_usage_deltas(sampling_duration = 1):
    """
    Helper function to get cpu usage deltas.
    
    Args:
        sampling_duration: time in seconds between the two collection.
        
    Returns:
        A dict containing cpu usage delta for each cpu
    """
    
    with open('/proc/stat') as f1:
        with open('/proc/stat') as f2:
            content1 = f1.read()  #read stat for first collection
            time.sleep(sampling_duration)
            content2 = f2.read()  #read stat for second collection
            
    cpu_count = multiprocessing.cpu_count()  #total number of cpu cores available
    deltas, lines1, lines2 = {}, content1.splitlines(), content2.splitlines()
    
    #if only one cpu available, read only the first line, else read total cpu count lines starting from the second line
    i, cpu_count = (1, cpu_count + 1) if cpu_count > 1 else (0, 1)
    
    #extract deltas
    while i < cpu_count:
        line_split1 = lines1[i].split()
        line_split2 = lines2[i].split()
        deltas[line_split1[0]] = [int(b) - int(a) for a, b in zip(line_split1[1:], line_split2[1:])]
        i += 1
    
    return deltas

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

def get_net_rw(interfaces = [], sampling_duration = 1):
    """
    Function to get network reads and writes for the duration given.
    
    Args:
        interfaces: the interfaces for which the collection should be done.
        sampling_duration: time in seconds between the two collection.
    
    Returns:
        tuple containing reads and writes
    """
        
    with open('/proc/net/dev') as f1:
        with open('/proc/net/dev') as f2:
            content1 = f1.read()
            time.sleep(sampling_duration)
            content2 = f2.read()
            
    data = dict(zip(interfaces, [dict(zip(['reads', 'writes'], [0, 0])) for interface in interfaces]))
            
    for line in content1.splitlines():
        for interface in [interface_x for interface_x in interfaces if interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = int(fields[0])
            data[interface]['writes'] = int(fields[8])
            break
    
    for line in content2.splitlines():
        for interface in [interface_x for interface_x in interfaces if interface_x in line]:
            fields = line.split('%s:' % interface)[1].split()
            data[interface]['reads'] = (int(fields[0]) - data[interface]['reads']) / float(sampling_duration)
            data[interface]['writes'] = (int(fields[8]) - data[interface]['writes']) / float(sampling_duration)
            break
    
    return data

def get_disk_rw(devices = [], sampling_duration = 1):
    """
    Function to get disk reads and writes for the duration given.
    
    Args:
        devices: devices for which the collection should be done.
        sampling_duration: time in seconds between the two collection.
    
    Returns:
        tuple containing reads and writes
    """
    
    with open('/proc/diskstats') as f1:
        with open('/proc/diskstats') as f2:
            content1 = f1.read()
            time.sleep(sampling_duration)
            content2 = f2.read()
            
    data = dict(zip(devices, [dict(zip(['reads', 'writes'], [0, 0])) for device in devices]))

    for line in content1.splitlines():
        for device in [device_x for device_x in devices if '%s ' % device_x in line]:
            fields = line.strip().split('%s ' % device)[1].split()
            data[device]['reads'] = int(fields[0])
            data[device]['writes'] = int(fields[4])
            break
    
    for line in content2.splitlines():
        for device in [device_x for device_x in devices if '%s ' % device_x in line]:
            fields = line.strip().split('%s ' % device)[1].split()
            data[device]['reads'] = (int(fields[0]) - data[device]['reads']) / float(sampling_duration)
            data[device]['writes'] = (int(fields[4]) - data[device]['writes']) / float(sampling_duration)
            break            
            
    return data

