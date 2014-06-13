"""
Abstracts activity execution.
Implements JobStatus, Job, Executer, JobProducer and JobConsumer
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import logging
import threading
import time
import subprocess
import re
import signal
import os
import tempfile
import globals
from constructs import *

_log = logging.getLogger(__name__)  #module level logging

class JobStatus(Namespace):
    """
    Used as an enumeration of job state
    """
    
    INITIALIZED = 0  #the initial state when job is instantiated
    BLOCKED = 1  #job has been blocked by whitelist
    RUNNING = 2  #job is in running state
    TIMED_OUT = 3  #job didnt finish in the timeout
    FINISHED = 4  #job finished
    
class Job:    
    """
    Represents a job, that can be executed
    """
    
    def __init__(self, activity, store):
        """
        Constructor
        
        Args:
            activity: dict representing the activity to be executed
            store: Storage instance used to post data
        """
        
        self.is_whitelisted = activity['is_whitelisted']  #is this job allowed to execute
        self.exec_timestamp = activity['next_exec_timestamp']  #timestamp at which the job should execute
        self.status = JobStatus.INITIALIZED  #current job state
        self.is_plugin = True if activity['details']['service'] == 'Plugins' else False  #is this job a plugin or a commandline
        
        #dict containing job execution details
        self.exec_details = {
            'timestamp': 0,  #actual timestamp when the job started
            'output': None,  #output of the job, file handle for commandline job, dict for successful pugin execution, str for failed pugin execution. 
            'pid': -1,  #process id if it is a commandline job
            'return_code': 0,  #return code of the job
            '_id': activity['details']['_id'],  #activity id
            'command': activity['details']['command']  #command to be executed for commandline job, else the python module name for plugin job
        }
        
        self.store = store  #Storage instance used to post data

    def prepare(self):
        """
        Public method to prepare the job for execution.
        This sets the execution timestamp.
        
        Returns:
            Execution start timestamp of the job
        """
        
        t = int(time.time() * 1000)
        self.exec_details['timestamp'] = t  #set the exec timestamp

        if self.is_whitelisted == True:  #if the job is whitelisted
            _log.debug('Executing activity(%s @ %d)' % (self.exec_details['_id'], t))
            
            #if it is not a plugin job, then we create a temperory file to capture the output
            #a plugin job return the data directly
            if not self.is_plugin:
                self.exec_details['output'] = tempfile.NamedTemporaryFile(dir = globals.Globals().temp_path)
                
            self.status = JobStatus.RUNNING  #change the state to running
        else:
            _log.info('Activity %s is blocked by whitelist' % self.exec_details['_id'])
            self.status = JobStatus.BLOCKED  #change the state to blocked

        return t

    def kill(self):
        """
        Public method to kill the job
        
        Returns:
            True on success else False
        """
        
        self.status = JobStatus.TIMED_OUT  #change the state to timed out
        
        try:            
            if self.exec_details['pid'] == -1:
                raise
            
            #kill the job, it is possible that the pid does not exist by the time we execute this statement
            os.kill(self.exec_details['pid'], signal.SIGTERM) 
        except:
            return False
        
        return True
        
    def update(self, details):
        """
        Public method to update execution details fo the job 
        
        Args:
            details: dict containing the details to be updated
        """
        
        if type(details) is dict:
            self.exec_details.update(details)
        
            if 'return_code' in details:  #if return_code is in the details then we assume the the job is finished
                self.status = JobStatus.FINISHED 

    def post_output(self):
        """
        Public method to post the output to storage
        """
        
        data = None

        if self.status == JobStatus.RUNNING and self.exec_details['pid'] == -1:  #commandline job who's pid is unknown
            data = {'timestamp': self.exec_details['timestamp'], 'returnCode': 0, 'data': 'Failed to retreive execution status.'}
        elif self.status == JobStatus.BLOCKED:  #commandline job that is blocked by whitelist
            data = {'timestamp': self.exec_details['timestamp'], 'returnCode': 0, 'data': 'Command blocked by whitelist.'}
        elif self.status == JobStatus.TIMED_OUT:  #job that failed to complete execution in given time
            data = {'timestamp': self.exec_details['timestamp'], 'returnCode': 0, 'data': 'Command exceeded timeout.'}
        elif self.status == JobStatus.FINISHED and self.exec_details['output']:  #a finished job with valid output
            data = {
                'timestamp': self.exec_details['timestamp'], 
                'returnCode': self.exec_details['return_code']
            }
            
            if self.is_plugin:  #for a plugin job, output is the data
                data['data'] = self.exec_details['output']
            else:
                #for a commandline job, output is the file containing data
                self.exec_details['output'].seek(0, os.SEEK_SET)
                data['data'] = self.exec_details['output'].read(256 * 1024)
                
                if not data['data']:  #if the file is empty
                    data['data'] = 'No output produced'
                    _log.debug('No output/error found for activity (%s @ %d)' % (self.exec_details['_id'], self.exec_details['timestamp']))
                
        self.close_file()  #close the file so that it is removed from the disk

        if data:  #push the data to store
            _log.debug('Pushing activity (%s @ %d) to %s' % (self.exec_details['_id'], self.exec_details['timestamp'], self.store.__class__.__name__))
            self.store.push(self.exec_details['_id'], data)

    def close_file(self):
        """
        Public method to close the output file if any
        """
        
        try:
            #close the file. it is possible that output is not a file, in that case it will raise an exception which is ignored
            self.exec_details['output'].close()
            os.remove(self.exec_details['output'].name)
        except:
            pass
        
        self.exec_details['output'] = None
    
class Executer(ThreadEx):
    """
    A wrapper class that creates a bash subprocess for commandline job execution
    It executes the commandline by writing to the bash script and gets the status in a blocking read
    """
    
    jobs = {}  #dict to keep track of active jobs
    jobs_lock = threading.RLock()  #thread lock to manipulate jobs
    
    def __init__(self):
        """
        Constructor
        """
        
        ThreadEx.__init__(self)  #inititalize the base class
        self.exec_process = None  #bash process instance
        self.process_lock = threading.RLock()  #thread lock for bash process instance
        self.is_stop = False  #stop flag for the thread
        self.globals = globals.Globals()  #reference to Globals for optimized access
        self.globals.event_dispatcher.bind('terminate', self.stop)  #bind to terminate event so that we can terminate bash process
        
        #use the job timeout defined in the config if we have one
        try:
            self.timeout = self.globals.config.sealion.commandTimeout
        except:
            self.timeout = 30

        self.timeout = int(self.timeout * 1000)  #convert to millisec
        
    def add_job(self, job):
        """
        Public method to execute the job.
        This method writes the commandline job to bash, it directly executes the plugin job.
        
        Args:
            job: the job to be executed
        """
        
        Executer.jobs_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        time.sleep(0.001)  #sleep for a millisec so that we dont end up with multiple jobs wih same timestamp
        
        #prepare the job and add it to the dict
        t = job.prepare()
        Executer.jobs['%d' % t] = job
        
        Executer.jobs_lock.release()  #we can safely release the lock as the rest the code in the function need not be atomic
        
        if job.is_plugin == False:  #write commandline job to bash
            self.write(job)
        else:            
            try:
                #we load the plugin and calls the get_data function and updates the job with the data
                #this can raise exception
                plugin = __import__(job.exec_details['command'])
                job.update({'return_code': 0, 'output': plugin.get_data()})
            except Exception as e:
                #on failure we set the return_code to non zero so that output can be interpreted as error string
                job.update({'return_code': 1, 'output': unicode(e)})
        
    def update_job(self, timestamp, details):
        """
        Public method to update the job with the details
        
        Args:
            timestamp: timestamp of the job to be updated
            details: dict containing the details to be updated
        """
        
        Executer.jobs_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        Executer.jobs['%d' % timestamp].update(details)
        Executer.jobs_lock.release()

    def finish_jobs(self):
        """
        Public method to get a list of finished jobs.
        A side effect of this method is that it kills any job exceeding the timeout
        
        Returns:
            The list of finished jobs.
        """
        
        finished_jobs = []  #list of finished jobs
        Executer.jobs_lock.acquire()   #this has to be atomic as multiple threads reads/writes
        t = int(time.time() * 1000)  #get the timestamp so that we can check the timeout

        for job_timestamp in Executer.jobs.keys():  #loop throgh the jobs
            job = Executer.jobs[job_timestamp]
            
            if t - job.exec_details['timestamp'] > self.timeout:  #if it exceeds the timeout
                job.kill() and _log.info('Killed activity (%s @ %d) as it exceeded timeout' % (job.exec_details['_id'], job.exec_details['timestamp']))

            #collect the job if it is not running and remove it from the dict
            if job.status != JobStatus.RUNNING:
                finished_jobs.append(job)
                del self.jobs[job_timestamp]

        Executer.jobs_lock.release()
        return finished_jobs
        
    def exe(self):
        "Method executes in a new thread."
        
        while 1:
            self.read()  #blocking read from bash suprocess
            
            if self.is_stop:  #should we stop now
                _log.debug('%s received stop event' % self.name)
                break
            
    @property
    def process(self):
        """
        Property to get the bash process instance
        
        Returns:
            Bash process instance
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes
 
        #self.wait returns True if the bash suprocess is terminated, in that case we will create a new bash process instance
        if self.wait() and self.is_stop == False:
            self.exec_process = subprocess.Popen(['bash', globals.Globals().exe_path + 'src/execute.sh'], stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, preexec_fn = os.setpgrp, bufsize = 1)
        
        self.process_lock.release()
        return self.exec_process
    
    def write(self, job):
        """
        Public method to write the commandline job to the bash subprocess
        
        Args:
            job: the commandline job to be executed
            
        Returns:
            True on success else False
        """
        
        try:
            #it is possible that the pipe is broken or the subprocess was terminated
            self.process.stdin.write('%d %s: %s\n' % (job.exec_details['timestamp'], job.exec_details['output'].name, job.exec_details['command']))
        except:
            return False
        
        return True
        
    def read(self):
        """
        Method to read from bash subprocess and update the job details
        
        Returns:
            True on success else False
        """
        
        try:
            #it is possible that the pipe is broken or the subprocess was terminated
            data = self.process.stdout.readline().split()
            self.update_job(int(data[0]), {data[1]: data[2]})
        except:
            return False
        
        return True
        
    def wait(self, is_force = False): 
        """
        Method to wait for the bash subprocess if it was terminated, to avoid zombies
        This method is not thread safe.
        
        Args:
            is_force: if it is True, it terminates the process before waiting
            
        Returns:
            True if the process is terminated else False
        """
        
        is_terminated = True  #is the bash subprocess terminated
        
        try:
            if self.exec_process.poll() == None:  #if the process is running
                if is_force:  #kill the process
                    os.kill(self.exec_process.pid, signal.SIGTERM)
                else:
                    is_terminated = False  #process still running
                
            #wait for the process if it is terminated
            if is_terminated == True:
                os.waitpid(self.exec_process.pid, os.WUNTRACED)
                self.exec_process.stdin.close()
                self.exec_process.stdout.close()
        except:
            pass
                
        return is_terminated
        
    def stop(self, *args, **kwargs):
        """
        Public method to stop the thread.
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        self.is_stop = True
        self.wait(True)  #terminate the bash subprocess and wait
        self.process_lock.release()
        
class JobProducer(SingletonType('JobProducerMetaClass', (ThreadEx, ), {})):
    """
    Produces job for an activity and schedules them using a queue.
    """
    
    def __init__(self, store):
        """
        Constructor
        
        Args:
            store: Storage instance.
        """
        
        ThreadEx.__init__(self)  #initialize the base class
        self.globals = globals.Globals()  #store reference to Globals for optmized access
        self.activities_lock = threading.RLock()  #threading lock for updating activities
        self.activities = {}  #dict of activities 
        self.queue = queue.Queue()  #job queue
        self.sleep_interval = 5  #how much time should the thread sleep before scheduling
        self.store = store  #storage instance
        self.consumer_count = 0  #total number of job consumers running
        self.executer = Executer()  #executer instance for running commandline activities
        self.globals.event_dispatcher.bind('get_activity_funct', self.get_activity_funct)

    def is_in_whitelist(self, activity):
        """
        Method checks whether an activity is allowed to run by looking up in a whitelist
        
        Args:
            activity: dict representing the activity to be checked
            
        Returns:
            True if the activity is whitelsited else False
        """
        
        whitelist, command = [], activity['command']
        
        if activity['service'] == 'Plugins':  #always execute plugin activities
            return True

        if hasattr(self.globals.config.sealion, 'whitelist'):  #read the whitelist from config
            whitelist = self.globals.config.sealion.whitelist
            
        is_whitelisted = False if len(whitelist) else True  #an empty whitelist implies that all activities are allowed to run

        #find out whether the activity is whitelisted
        for i in range(0, len(whitelist)):
            if re.match(whitelist[i], command):
                is_whitelisted = True
                break

        return is_whitelisted

    def schedule_activities(self):
        """
        Method to schedule the activity based on their interval
        """
        
        self.activities_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        t, jobs = time.time(), []

        for activity_id in self.activities:
            activity = self.activities[activity_id]

            #whether the activity interval expired
            #we have to put the job in the queue if the execution timestamp comes before the scheduler runs again
            if activity['next_exec_timestamp'] <= t + self.sleep_interval:
                jobs.append(Job(activity, self.store))  #add a job for the activity
                activity['next_exec_timestamp'] = activity['next_exec_timestamp'] + activity['details']['interval']  #update the next execution timestamp

        jobs.sort(key = lambda job: job.exec_timestamp)  #sort the jobs based on the execution timestamp
        len(jobs) and _log.debug('Scheduling %d activities', len(jobs))

        for job in jobs:  #scheudle the jobs
            self.queue.put(job)

        self.activities_lock.release()
        
    def set_activities(self, *args, **kwargs):
        """
        Method updates the dict containing the activities.
        It also starts Job consumers
        """
        
        activities = self.globals.config.agent.activities
        start_count, update_count, stop_count, plugin_count, activity_ids = 0, 0, 0, 0, []
        self.activities_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        t = time.time()  #current time is the next execution time for any activity started or updated
        
        for activity in activities:
            activity_id = activity['_id']
            cur_activity = self.activities.get(activity_id)
            
            if cur_activity:  #if we already have the activity in the dict
                details = cur_activity['details']
                
                #if interval or command modified
                if details['interval'] != activity['interval'] or details['command'] != activity['command']:
                    cur_activity['details'] = activity
                    cur_activity['is_whitelisted'] = self.is_in_whitelist(activity)  #check whether the activity is allowed to run
                    cur_activity['next_exec_timestamp'] = t  #execute the activity immediately
                    _log.info('Updating activity %s' % activity_id)
                    update_count += 1
            else:
                #add a new activity
                self.activities[activity_id] = {
                    'details': activity,
                    'is_whitelisted': self.is_in_whitelist(activity),  #check whether the activity is allowed to run
                    'next_exec_timestamp': t  #execute the activity immediately
                }
                _log.info('Starting activity %s' % activity_id)
                start_count += 1
            
            plugin_count += 1 if activity['service'] == 'Plugins' else 0  #count the number of plugins, it affect the number of job consumers
            activity_ids.append(activity_id)  #keep track of available activity ids
            
        #find any activities in the dict that is not in the activity_ids list
        deleted_activity_ids = [activity_id for activity_id in self.activities if activity_id not in activity_ids]
        
        #delete the activities from the dict
        for activity_id in deleted_activity_ids:
            _log.info('Stopping activity %s' % activity_id)
            del self.activities[activity_id]
            stop_count += 1
            
        self.store.clear_offline_data(activity_ids)  #delete any activites from offline store if it is not in current activity list
        self.activities_lock.release()
        
        #calculate the job consumer count and run the required number of job consumers
        #it assumes that every plugin activity gets an individual thread and all commandline activities shares one thread
        consumer_count = (1 if len(activity_ids) - plugin_count > 0 else 0) + plugin_count
        self.start_consumers(consumer_count)    
        self.stop_consumers(consumer_count)
        
        if start_count + update_count > 0:  #immediately schedule any added/updated activities
            self.schedule_activities()
        
        _log.info('%d started; %d updated; %d stopped' % (start_count, update_count, stop_count))
        
    def exe(self):        
        """
        Method runs in a new thread.
        """
        
        self.executer.start()  #start the executer for bash suprocess
        self.set_activities();  #set ativities dict
        self.globals.event_dispatcher.bind('set_activities', self.set_activities)  #bind to 'set_activities' event so that we can update our activities dict
        
        while 1:  #schedule the activities every sleep_interval seconds
            self.schedule_activities()
            self.globals.stop_event.wait(self.sleep_interval)

            if self.globals.stop_event.is_set():  #do we need to stop
                _log.debug('%s received stop event' % self.name)
                break

        self.stop_consumers()  #stop the consumers
        
    def start_consumers(self, count):
        """
        Method to start job consumers.
        
        Args:
            count: count of total consumers to run
        """
        
        count = min(8, count)  #limit the number of consumers
        count - self.consumer_count > 0 and _log.info('Starting %d job consumers' % (count - self.consumer_count))
        
        while self.consumer_count < count:  #start consumers
            self.consumer_count += 1
            JobConsumer().start()

    def stop_consumers(self, count = 0):
        """
        Method to stop job consumers.
        
        Args:
            count: count of total consumers to run
        """
        
        self.consumer_count - count > 0 and _log.info('Stopping %d job consumers' % (self.consumer_count - count))
        
        while self.consumer_count > count:  #stop consumers
            self.queue.put(None)  #put None in the job queue and the job consumer getting it will stop
            self.consumer_count -= 1
            
    def get_activity_funct(self, *args, **kwargs):
        """
        Callback method to supply get_activity function
        """
        
        callback = args[1]
        callback(self.get_activity)
                
    def get_activity(self, activity):
        """
        Method to get acitity from the dict
        """
        
        self.activities_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:      
            return self.activities.get(activity)
        finally:
            self.activities_lock.release()

class JobConsumer(ThreadEx):
    """
    Class to consume the jobs produced in the queue
    """
    
    unique_id = 1  #unique id for consumers
    
    def __init__(self):
        """
        Constructor
        """
        
        ThreadEx.__init__(self)  #initialize the base class
        self.job_producer = JobProducer()  #job producer
        self.globals = globals.Globals()  #save the reference to Globals for optimized access
        self.name = '%s-%d' % (self.__class__.__name__, JobConsumer.unique_id)  #set the name
        JobConsumer.unique_id += 1  #increment the id

    def exe(self):       
        while 1:  #wait on job queue
            job = self.job_producer.queue.get()  #blocking wait

            if self.globals.stop_event.is_set() or job == None:  #need to stop
                _log.debug('%s received stop event' % self.name)
                break

            t = time.time()  #get the current time
            job.exec_timestamp - t > 0 and time.sleep(job.exec_timestamp - t)  #sleep till the execution time reaches
            self.job_producer.executer.add_job(job)  #add the job to executer
