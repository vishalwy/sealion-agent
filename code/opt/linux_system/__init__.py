import re
import os
from . import linux_metrics as lm

def get_data():
    data = {
        'loadAvg1Min': 0,
        'loadAvg5Min': 0,
        'loadAvg15Min': 0,
        'cpuUsage': [],
        'memUsage': {},
        'networkReads': [],
        'networkWrites': [],
        'diskReads': [],
        'diskWrites': []
    }
    
    data.update(dict(zip(['loadAvg1Min', 'loadAvg5Min', 'loadAvg15Min'], lm.cpu_stat.load_avg())))
    
    for file in os.listdir('/sys/class/net/'):
        if file != 'lo':
            interface = file
            network_reads, network_writes = lm.net_stat.rx_tx_bytes_persec(interface)
            data['networkReads'].append({'name': interface, 'value': network_reads})
            data['networkWrites'].append({'name': interface, 'value': network_writes})
    
    with open('/proc/partitions', 'r') as f:
        for line in re.findall('^\s*[0-9]+\s+[1-9]+.*$', f.read(), flags = re.MULTILINE):
            device = re.search('\s([^\s]+)$', line).group(1).strip()
            disk_reads, disk_writes = lm.disk_stat.disk_reads_writes_persec(device)
            data['diskReads'].append({'name': device, 'value': disk_reads})
            data['diskWrites'].append({'name': device, 'value': disk_writes})
    
    return data
