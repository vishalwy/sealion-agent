"""
Plugin to collect Linux system metrics.
This module should have get_data function that returns the data.
"""

import re
import os
import multiprocessing
import time

class NetError(Exception):
    """
    Class representing network releated exception.
    """
    
    pass

class DiskError(Exception):
    """
    Class representing disk releated exception.
    """
    
    pass

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
    for file in os.listdir('/sys/class/net/'):
        if file != 'lo':
            interface = file
            network_reads, network_writes = get_net_rw(interface)  #get reads and writes for this interface
            data['networkReads'].append({'name': interface, 'value': network_reads})
            data['networkWrites'].append({'name': interface, 'value': network_writes})
    
    #find disk read and write for each logical disk
    with open('/proc/partitions') as f:
        for line in re.findall('^\s*[0-9]+\s+[1-9]+.*$', f.read(), flags = re.MULTILINE):
            device = re.search('\s([^\s]+)$', line).group(1).strip()
            disk_reads, disk_writes = get_disk_rw(device)  #get reads and writes for this partition
            data['diskReads'].append({'name': device, 'value': disk_reads})
            data['diskWrites'].append({'name': device, 'value': disk_writes})
    
    return data

def get_load_avg():
    """
    Function to get load avg.
    
    Returns:
        
    """
    
    with open('/proc/loadavg') as f:
        line = f.readline()
    
    return [float(x) for x in line.split()[:3]]

def get_cpu_usage(sampling_duration = 1):
    keys = ['us', 'ni', 'sy', 'id', 'wa', 'hi', 'si', 'st']
    deltas = get_cpu_usage_deltas(sampling_duration)
    ret = {}
    
    for key in deltas:
        total = sum(deltas[key])
        ret[key] = dict(zip(keys, [100 - (100 * (float(total - x) / total)) for x in deltas[key]]))
        del ret[key]['hi']
        del ret[key]['si']
    
    return  ret

def get_cpu_usage_deltas(sampling_duration = 1):
    with open('/proc/stat') as f1:
        with open('/proc/stat') as f2:
            content1 = f1.read()
            time.sleep(sampling_duration)
            content2 = f2.read()
            
    cpu_count = multiprocessing.cpu_count()
    deltas, lines1, lines2 = {}, content1.splitlines(), content2.splitlines()
    i, cpu_count = (1, cpu_count + 1) if cpu_count > 1 else (0, 1)
    
    while i < cpu_count:
        line_split1 = lines1[i].split()
        line_split2 = lines2[i].split()
        deltas[line_split1[0]] = [int(b) - int(a) for a, b in zip(line_split1[1:], line_split2[1:])]
        i += 1
    
    return deltas

def get_mem_usage():
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

def get_net_rw(interface, sampling_duration = 1):
    with open('/proc/net/dev') as f1:
        with open('/proc/net/dev') as f2:
            content1 = f1.read()
            time.sleep(sampling_duration)
            content2 = f2.read()
            
    for line in content1.splitlines():
        if interface in line:
            found = True
            data = line.split('%s:' % interface)[1].split()
            r_bytes1 = int(data[0])
            w_bytes1 = int(data[8])
            break
    
    if not found:
        raise NetError('interface not found: %r' % interface)
    
    for line in content2.splitlines():
        if interface in line:
            found = True
            data = line.split('%s:' % interface)[1].split()
            r_bytes2 = int(data[0])
            w_bytes2 = int(data[8])
            break
    
    r_bytes_per_sec = (r_bytes2 - r_bytes1) / float(sampling_duration)
    w_bytes_per_sec = (w_bytes2 - w_bytes1) / float(sampling_duration)   
    return (r_bytes_per_sec, w_bytes_per_sec)

def get_disk_rw(device, sampling_duration = 1):
    with open('/proc/diskstats') as f1:
        with open('/proc/diskstats') as f2:
            content1 = f1.read()
            time.sleep(sampling_duration)
            content2 = f2.read()
    sep = '%s ' % device
    found = False
    for line in content1.splitlines():
        if sep in line:
            found = True
            fields = line.strip().split(sep)[1].split()
            num_reads1 = int(fields[0])
            num_writes1 = int(fields[4])
            break
            
    if not found:
        raise DiskError('device not found: %r' % device)
    
    for line in content2.splitlines():
        if sep in line:
            fields = line.strip().split(sep)[1].split()
            num_reads2 = int(fields[0])
            num_writes2 = int(fields[4])
            break            
    reads_per_sec = (num_reads2 - num_reads1) / float(sampling_duration)
    writes_per_sec = (num_writes2 - num_writes1) / float(sampling_duration)   
    return (reads_per_sec, writes_per_sec)
