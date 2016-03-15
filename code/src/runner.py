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
import re
import signal
import os
import sys
import json
import helper
import universal
import extract
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
    IGNORED = 5  #job should be considered as ignored and should not process the output
    
class Extractor(WorkerProcess):
    """
    A wrapper class that creates a python subprocess for extracting the metrics from the output
    It executes the commandline by writing to the bash script and gets the status in a blocking read.
    For more details checkout extract.py
    """
    
    metrics = {}  #previous value for cumulative metrics calculation; being a class variable gives the possiblity of scaling it to multiple processes
    metrics_lock = threading.RLock()  #thread lock to manipulate cumulative metrics
    
    def __init__(self):
        """
        Constructor
        """
        
        self.univ = universal.Universal()
        self.extract_lock = threading.RLock()  #for limiting access to extractor process
        
        #use the metric timeout defined in the config if we have one
        try:
            self.timeout = self.univ.config.sealion.metricTimeout
        except:
            self.timeout = 2
        
        #initialize the worker process with the python executable and arguments, this doesn't start the process
        WorkerProcess.__init__(self, sys.executable, '%s/src/extract.py' % self.univ.exe_path, '%s' % self.timeout)
        
    def extract(self, job, output):
        """
        Public method to extract the metrics from the output given

        Args:
            job: Job object for the command executed
            output: command output to be parsed

        Returns:
            dict representing the metrics extracted, None if no metrics
        """
        
        metrics, job_str = job.exec_details['activity'].get('metrics', {}), unicode(job)
        return_code, data = job.exec_details['return_code'], None
        
        if not metrics:  #if no metrics
            return None
        elif not self.timeout:  #if no timeout defined, means the extraction should be performed within
            data = extract.extract_metrics(output, return_code, metrics, job_str)
        else:
            #acquire the lock otherwise the order of the output read can mix up with another activity's metric
            self.extract_lock.acquire()  

            #write to the subprocess and on successful write, start processing the output
            if self.write(json.dumps({'output': output, 'return_code': return_code, 'metrics': metrics, 'job': job_str})):
                while 1:
                    line = self.read()  #blocking read
                    
                    #unsuccesful read due to various reasons, and hence no metrics
                    if line == None:
                        break;

                    data = line.split(' ', 1)  #split the line into two to find out the header format

                    if data[0] == 'debug:':  #a debug statement
                        _log.debug(data[1])
                    elif data[0] == 'data:':  #data
                        try:
                            data = json.loads(data[1])  #try to parse the json
                        except Exception as e:
                            _log.error('Failed to extract metrics from %s; %s' % (job_str, unicode(e)))
                            data = None  

                        break  #in any case, break as there is nothing more to read
                    elif line:
                        _log.error(line)

            self.extract_lock.release()  #release the lock
            self.limit_process_usage(2222)
            
        try:  #it could be possible the values are not in proper format
            Extractor.metrics_lock.acquire()
        
            for metric_id in data:
                #set the value based on the cumulative nature of the metric
                if metrics[metric_id]['cumulative']:
                    value = data[metric_id]
                    data[metric_id] = value - Extractor.metrics.get(metric_id, value)
                    Extractor.metrics[metric_id] = value  #save the current value for next evaluation
                    
            return data
        except:
            return None
        finally:
            Extractor.metrics_lock.release()
    
class Job:    
    """
    Represents a job, that can be executed
    """
    
    extractor = Extractor()  #to extract the metrics
    
    def __init__(self, activity):
        """
        Constructor
        
        Args:
            activity: dict representing the activity to be executed
        """
        
        self.is_whitelisted = activity['is_whitelisted']  #is this job allowed to execute
        self.exec_timestamp = activity['next_exec_timestamp']  #timestamp at which the job should execute
        self.status = JobStatus.INITIALIZED  #current job state
        
        #is this job a plugin or a commandline; this can also point to a generator instance which indicates a job that has been started already 
        #so, False means its a commandline job, anything else means it is a plugin job
        self.plugin = True if activity['details'].get('service') == 'Plugins' else False  
        
        #dict containing job execution details
        self.exec_details = {
            'timestamp': 0,  #actual timestamp when the job started
            'output': None,  #output of the job, file handle for commandline job, dict for successful pugin execution, str for failed pugin execution. 
            'pid': -1,  #process id if it is a commandline job
            'return_code': 0,  #return code of the job
            'activity': activity['details'],  #activity the job represents
        }
        
        self.univ = universal.Universal()  #reference to Universal for optimized access
        
    def __str__(self):
        """
        String representation for the object
        
        Returns:
            A readable string representation
        """
        
        return helper.format_job(self.exec_details['activity']['_id'], self.exec_details['timestamp'])
    
    def prepare(self):
        """
        Public method to prepare the job for execution.
        This sets the execution timestamp.
        
        Returns:
            Execution start timestamp of the job
        """
        
        #if the timestamp is already there; do not prepare again
        if self.exec_details['timestamp']:
            return self.exec_details['timestamp']
        
        t = int(time.time() * 1000)
        self.exec_details['timestamp'] = t  #set the exec timestamp

        if self.is_whitelisted == True:  #if the job is whitelisted
            _log.debug('Executing %s' % self)
            
            #if it is not a plugin job, then we create a temperory file to capture the output
            #a plugin job return the data directly
            if self.plugin == False:
                self.exec_details['output'] = '%d' % t
                
            self.status = JobStatus.RUNNING  #change the state to running
        else:
            _log.info('Activity %s is blocked by whitelist' % self.exec_details['activity']['_id'])
            self.status = JobStatus.BLOCKED  #change the state to blocked

        return t

    def kill(self):
        """
        Public method to kill the job
        
        Returns:
            True on success else False
        """
        
        try:            
            if self.exec_details['pid'] == -1:
                raise
            
            #kill the job and change the state to timed out
            #it is possible that the pid does not exist by the time we execute this statement
            os.kill(self.exec_details['pid'], signal.SIGTERM) 
            self.status = JobStatus.TIMED_OUT
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
            try:
                details['pid'] = int(details['pid'])
            except:
                pass
            
            self.exec_details.update(details)
        
            if 'return_code' in details:  #if return_code is in the details then we assume the the job is finished
                self.status = JobStatus.FINISHED 
                
    def get_data(self):
        """
        Public method to get the data.
        
        Returns:
            Dict containing the data to be posted on success, else None.
            The data key holds either the method to read ouput or a dict if it is a plugin activity or a string
        """
        
        data = None

        if self.status == JobStatus.RUNNING and self.plugin == False and self.exec_details['pid'] == -1:  #commandline job who's pid is unknown
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
            
            if self.plugin == False:
                #for a commandline job, output is the file containing data
                #we supply the instance method to read the output on demand
                #this reduces the memory used unneceserily reading the output and putting it in the queue
                data['data'] = self.read_output
            else:  #for a plugin job, output is the data
                data['data'] = self.exec_details['output']
                data['metrics'] = self.exec_details.get('metrics')
        else:
            format = 'No data for %(activity)s; satus: %(status)d; pid: %(pid)d; output: %(output)s'
            format_spec = {
                'activity': self,
                'status': self.status,
                'pid': self.exec_details['pid'],
                'output': True if self.exec_details['output'] else False
            }
            _log.error(format % format_spec)
                
        return data

    def read_output(self):
        """
        Public method to read the output for commandline job.
        A side effect of this method is that it removes any ouput file, so that next attempt will return empty string.
        
        Returns:
            Output read, metrics if any
        """
        
        try:
            metrics = None  #metrics extracted from the output
            
            #for a commandline job, output is the file containing data
            output_file = open('%s/%s' % (self.univ.temp_path, self.exec_details['output']), 'rb')
            output = output_file.read(256 * 1024).decode('utf-8', 'replace')
            output_file.close()

            if not output:  #if the file is empty
                output = 'No output/error produced'
                _log.debug('No output/error found for %s' % self)
            else:
                _log.debug('Read output from %s' % self)
                metrics = Job.extractor.extract(self, output)  #extract the metric from the valid output
        except Exception as e:
            output = 'Could not read output'
            _log.error('Failed to read output from %s; %s' % (self, unicode(e)))
            
        self.remove_file()  #remove the output file
        return output, metrics
    
    def remove_file(self):
        """
        Public method to delete output file if any
        """
        
        try:
            #it is possible that output is not a file, in that case it will raise an exception which is ignored
            os.remove('%s/%s' % (self.univ.temp_path, self.exec_details['output']))
            _log.debug('Removed the output file for %s' % self)
        except:
            pass
        
        self.exec_details['output'] = None
            
class Executer(WorkerProcess, ThreadEx):
    """
    A wrapper class that creates a bash subprocess for commandline job execution
    It executes the commandline by writing to the bash script and gets the status in a blocking read.
    For more details checkout execute.sh
    """
    
    jobs = {}  #dict to keep track of active jobs; being a class variable gives the possiblity of scaling it to multiple processes
    jobs_lock = threading.RLock()  #thread lock to manipulate jobs
    
    def __init__(self):
        """
        Constructor
        """
        
        self.univ = universal.Universal()  #reference to Universal for optimized access
        self.env_variables = {}  #env variables received from the server to execute commands
        ThreadEx.__init__(self)  #inititalize thread base class
        
        #inititalize process base class; refer execute.sh to read more about arguments to be passed in 
        exec_args = ['bash', '%s/src/execute.sh' % self.univ.exe_path, self.univ.main_script]
        os.isatty(sys.stdin.fileno()) or exec_args.append('1')
        WorkerProcess.__init__(self, *exec_args)
        
        self.daemon = True  #run this thread as daemon as it should not block agent from shutting down
        self.univ.event_dispatcher.bind('terminate', self.stop)  #bind to terminate event so that we can terminate bash process
        
        #use the job timeout defined in the config if we have one
        try:
            self.timeout = self.univ.config.sealion.commandTimeout
        except:
            self.timeout = 30

        self.timeout = int(self.timeout * 1000)  #convert to millisec
        
    def __str__(self):
        """
        String representation for the object
        
        Returns:
            A readable string representation
        """
        
        return WorkerProcess.__str__(self)
        
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
        
        if job.plugin == False:  #write commandline job to bash
            self.write(job.exec_details)
        else:            
            try:
                #we load the plugin and calls the get_data generator
                #this can raise exception
                if job.plugin == True:
                    activity = job.exec_details['activity']
                    
                    #get_data which should be written as a plugin
                    job.plugin = __import__(activity['command']).get_data(activity.get('metrics', {}))
                    
                try:
                    data = next(job.plugin)  #get next value from the generator
                except (StopIteration, GeneratorExit):
                    pass
                    
                #if the data returned is int, schedule it after that many seconds
                if type(data) is int:
                    job.exec_timestamp += data
                    JobProducer().queue.put(job)
                else:
                    job.update({'return_code': 0, 'output': data['output'], 'metrics': data.get('metrics')})
            except Exception as e:
                #on failure we set the status code as ignored, so that output is not processed
                job.status = JobStatus.IGNORED
                _log.error('Failed to get data for plugin %s; %s' % (job, unicode(e)))
        
    def update_job(self, timestamp, details):
        """
        Public method to update the job with the details
        
        Args:
            timestamp: timestamp of the job to be updated
            details: dict containing the details to be updated
        """
        
        Executer.jobs_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            Executer.jobs['%d' % timestamp].update(details)
        except KeyError:
            pass  #it is possible that bash returns a process timestamp that has been killed already
        finally:
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

        for job_timestamp in list(Executer.jobs.keys()):  #loop throgh the jobs
            job = Executer.jobs[job_timestamp]

            #calculate the timeout in way that similar activities wont overlap
            timeout = min(job.exec_details['activity']['interval'] * 1000, self.timeout)  
            
            #if the job exceeds the timeout
            if job.status == JobStatus.RUNNING and t - job.exec_details['timestamp'] > timeout:
                job.kill() and _log.info('Killed %s as it exceeded timeout' % job)

            if job.status == JobStatus.IGNORED:  #remove the job if it is to be ignored
                del Executer.jobs[job_timestamp]
            elif job.status != JobStatus.RUNNING:  #collect the job if it is not running and remove it from the dict
                finished_jobs.append(job)
                del Executer.jobs[job_timestamp]
                
        not finished_jobs and not Executer.jobs and self.limit_process_usage(2222)
        Executer.jobs_lock.release()
        finished_jobs and _log.info('Finished execution of %d activities' % len(finished_jobs))
        return finished_jobs
        
    def exe(self):
        """
        Method executes in a new thread.
        """
        
        while 1:
            self.read()  #blocking read from bash suprocess
            
            if self.is_stop:  #should we stop now
                _log.debug('%s received stop event' % self.name)
                break
    
    def init_process(self):
        """
        Method to initialize the bash subprocess
        """
        
        os.setpgrp()  #set process group
        os.chdir(self.univ.temp_path)  #change the working directory
        
        #export env variables
        #env variables defined in sealion config takes precedence over the ones in agent config
        os.environ.update(self.env_variables)
        os.environ.update(self.univ.config.sealion.get_dict(('env', {}))['env'])
    
    @staticmethod
    def format_job(job_details):
        """
        Method to get the formated string representing the commandline job
        
        Args:
            job_details: dict representing the commandline job to be stringified
            
        Returns:
            String representing the job to write to command line
        """
        
        activity = job_details.get('activity')
        format_args = (job_details['timestamp'], job_details['output'])
        
        if activity:
            format_args += (activity['_id'], activity['interval'], activity['command'])
        else:
            format_args += ('0', 0, job_details['command'])
        
        return '%d %s %s %s: %s' % format_args
    
    def write(self, job_details):
        """
        Public method to write the commandline job to the bash subprocess
        
        Args:
            job_details: dict representing the commandline job to be executed; this can also be a maintainance command.
            
        Returns:
            True on success else False
        """
        
        return WorkerProcess.write(self, Executer.format_job(job_details))  #call the baseclass version
        
    def read(self):
        """
        Method to read from bash subprocess and update the job details
        
        Returns:
            True on success else False
        """
        
        try:
            line = WorkerProcess.read(self)  #read from the base class
            
            if not line:
                return False
            
            data = line.split()
            
            if data[0] == 'warning:':  #bash has given some warning
                _log.warn(line[line.find(' ') + 1:])
            elif data[0] == 'data:':  #data
                self.update_job(int(data[1]), {data[2]: data[3]})
            else:  #everything else
                _log.error(line)
        except Exception as e:
            _log.error('Failed to read from %s; %s' % (self, unicode(e)))
            return False
        
        return True
        
    def stop(self, *args, **kwargs):
        """
        Public method to stop the thread.
        """
        
        WorkerProcess.stop(self)  #terminate the bash subprocess
        Executer.jobs_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        #loop throgh the jobs and remove temperory files
        for job_timestamp in list(Executer.jobs.keys()):  
            job = Executer.jobs[job_timestamp]
            job.remove_file()
        
        Executer.jobs_lock.release()
        
    def set_env_variables(self):
        """
        Method to set the env variables
        """
        
        set_vars, unset_count, export_count = [], 0, 0
        env_vars = self.univ.config.agent.get_dict((['config', 'envVariables'], {}))['envVariables']
        config_env_vars = self.univ.config.sealion.get_dict(('env', {}))['env']
        job_details = {'timestamp': 0, 'output': '/dev/stdout', 'command': 'export %s=\'%s\''}  #maintainance job
        
        #this has to be atomic as we want to update the env variables before executing the next job
        self.process_lock.acquire()  
        
        for env_var in env_vars:
            value = env_vars[env_var] 
            set_vars.append(env_var)
            
            if value == self.env_variables.get(env_var) or config_env_vars.get(env_var) != None:
                continue
            
            try:
                #update the env variable and export it to the curent bash process
                self.env_variables[env_var] = value
                job_details['command'] = 'export %s=\'%s\'' % (env_var, value.replace('\'', '\'\\\'\''))
                self.exec_process and self.write(job_details)
                export_count += 1
                _log.info('Exported env variable %s' % env_var)
            except Exception as e:
                _log.error('Failed to export env variable %s; %s' % (env_var, unicode(e)))
            
        #find any env vars in the dict that is not in the set variables list and reset/delete
        for env_var in [env_var for env_var in self.env_variables if env_var not in set_vars]:
            try:
                del self.env_variables[env_var]  #delete it from the env variables dict
                value = os.environ.get(env_var)  #we need to check whether this variable is available in os environ
                
                if value != None:  #if os environ has this value, then export that value rather than unsetting it
                    job_details['command'] = 'export %s=\'%s\'' % (env_var, value.replace('\'', '\'\\\'\''))
                    self.exec_process and self.write(job_details)
                    export_count += 1
                    _log.info('Exported env variable %s' % env_var)
                else:  #unset it from the curent bash process
                    job_details['command'] = 'unset %s' % env_var
                    self.exec_process and self.write(job_details)
                    unset_count += 1
                    _log.info('Unset env variable %s' % env_var)
            except Exception as e:
                _log.error('Failed to unset env variable %s; %s' % (env_var, unicode(e)))
            
        self.process_lock.release()
        _log.info('Env variables - %d exported; %d unset' % (export_count, unset_count))
        
class JobProducer(singleton(ThreadEx)):
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
        self.univ = universal.Universal()  #store reference to Universal for optmized access
        self.activities_lock = threading.RLock()  #threading lock for updating activities
        self.activities = {}  #dict of activities 
        self.queue = queue.Queue()  #job queue
        self.sleep_interval = 5  #how much time should the thread sleep before scheduling
        self.store = store  #storage instance
        self.consumer_count = 0  #total number of job consumers running
        self.executer = Executer()  #executer instance for running commandline activities
        self.univ.event_dispatcher.bind('get_activity_funct', self.get_activity_funct)

    def is_in_whitelist(self, activity):
        """
        Method checks whether an activity is allowed to run by looking up in a whitelist
        
        Args:
            activity: dict representing the activity to be checked
            
        Returns:
            True if the activity is whitelsited else False
        """
        
        if activity.get('service') == 'Plugins':  #always execute plugin activities
            return True
        
        whitelist, command = self.univ.config.sealion.get('whitelist', []) , activity['command']
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
                jobs.append(Job(activity))  #add a job for the activity
                activity['next_exec_timestamp'] = activity['next_exec_timestamp'] + activity['details']['interval']  #update the next execution timestamp

        jobs.sort(key = lambda job: job.exec_timestamp)  #sort the jobs based on the execution timestamp
        len(jobs) and _log.info('Scheduling %d activities', len(jobs))

        for job in jobs:  #scheudle the jobs
            self.queue.put(job)

        self.activities_lock.release()
        
    def set_exec_details(self, *args, **kwargs):
        """
        Method to updates the execution details for activities.
        This has to be performed in a thread safe manner as the activities depends on the environment variables.
        It also starts Job consumers
        """
        
        self.executer.set_env_variables()  #set the environment variables
        ret = self.set_activities()  #set activities
        
        #calculate the job consumer count and run the required number of job consumers
        #it assumes that every plugin activity gets an individual thread and all commandline activities shares one thread
        consumer_count = (1 if ret[0] - ret[1] > 0 else 0) + ret[1]
        self.is_alive() and self.start_consumers(consumer_count)    
        self.stop_consumers(consumer_count)
        ret[2] and self.schedule_activities()  #immediately schedule any added/updated activities
        
    @staticmethod
    def update_metrics(cur_activity, new_activity):
        """
        Static method to sanitize the parser code and log the details of added/updated/removed metrics
        
        Args:
            cur_activity: dict representing the activity
            new_activity: modified dict for the activity
            
        Returns:
            True if metric was added/removed/updated else False
        """
        
        cur_metrics, new_metrics = cur_activity.get('metrics', {}), new_activity.get('metrics', {})
        add_count, update_count, remove_count, activity_id, metric_ids = 0, 0, 0, new_activity['_id'], []
        
        #loop through new metrics updating the counts
        for new_metric in new_metrics:
            metric_id = new_metric
            new_metric = new_metrics[metric_id]
            cur_metric = cur_metrics.get(metric_id)
            
            if cur_metric:
                if cur_metric['parser'] != new_metric['parser'] or cur_metric['cumulative'] != new_metric['cumulative']:
                    new_metric['parser'] = extract.sanitize_parser(new_metric['parser'])  #sanitize upfront to optimize performance
                    update_count += 1
                    _log.info('Updated metric %s for activity %s' % (metric_id, activity_id))
            else:
                new_metric['parser'] = extract.sanitize_parser(new_metric['parser'])  #sanitize upfront to optimize performance
                add_count += 1
                _log.info('Added metric %s for activity %s' % (metric_id, activity_id))
                
            metric_ids.append(metric_id)
            
        #udate the remove count by looping through removed metrics
        for metric_id in [metric_id for metric_id in cur_metrics if metric_id not in metric_ids]:
            _log.info('Removed metric %s from activity %s' % (metric_id, activity_id))
            remove_count += 1
            
        return True if add_count or update_count or remove_count else False
        
    def set_activities(self):
        """
        Method updates the dict containing the activities.
        
        Returns:
            Tuple containing (total_count, plugin_count, start_count, update_count, stop_count)
        """
        
        activities = self.univ.config.agent.get(['config', 'activities'])
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
                    JobProducer.update_metrics(details, activity)
                    cur_activity['details'] = activity
                    cur_activity['is_whitelisted'] = self.is_in_whitelist(activity)  #check whether the activity is allowed to run
                    cur_activity['next_exec_timestamp'] = t  #execute the activity immediately
                    _log.info('Updated activity %s' % activity_id)
                    update_count += 1
                elif JobProducer.update_metrics(details, activity):
                    cur_activity['details'] = activity
            else:
                #add a new activity
                self.activities[activity_id] = {
                    'details': activity,
                    'is_whitelisted': self.is_in_whitelist(activity),  #check whether the activity is allowed to run
                    'next_exec_timestamp': t  #execute the activity immediately
                }
                JobProducer.update_metrics({}, activity)
                _log.info('Started activity %s' % activity_id)
                start_count += 1
            
            plugin_count += 1 if activity.get('service') == 'Plugins' else 0  #count the number of plugins, it affect the number of job consumers
            activity_ids.append(activity_id)  #keep track of available activity ids    
        
        #find any activities in the dict that is not in the activity_ids list and delete
        for activity_id in [activity_id for activity_id in self.activities if activity_id not in activity_ids]:
            del self.activities[activity_id]
            _log.info('Stopped activity %s' % activity_id)
            stop_count += 1
            
        self.store.clear_offline_data(activity_ids)  #delete any activites from offline store if it is not in current activity list
        self.activities_lock.release()
        _log.info('Activities - %d started; %d updated; %d stopped' % (start_count, update_count, stop_count))
        return len(activity_ids), plugin_count, start_count + update_count
        
    def exe(self):        
        """
        Method runs in a new thread.
        """
        
        self.executer.write({'timestamp': 0, 'output': '/dev/stdout', 'command': 'rm -rf ./*'})  #init command to remove temp files
        self.executer.start()  #start the executer for bash suprocess
        self.set_exec_details();  #set execution details such as env variables and commands to execute
        self.univ.event_dispatcher.bind('set_exec_details', self.set_exec_details)  #bind to the event triggered whenever the config updates
        
        while 1:  #schedule the activities every sleep_interval seconds
            self.schedule_activities()
            self.univ.stop_event.wait(self.sleep_interval)

            if self.univ.stop_event.is_set():  #do we need to stop
                _log.debug('%s received stop event' % self.name)
                break

        self.stop_consumers()  #stop the consumers
        Job.extractor.stop()  #stop extractor for metrics evaluation
        self.executer.stop()  #stop executer for subprocess
        
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
        self.univ = universal.Universal()  #save the reference to Universal for optimized access
        self.name = '%s-%d' % (self.__class__.__name__, JobConsumer.unique_id)  #set the name
        JobConsumer.unique_id += 1  #increment the id

    def exe(self):       
        while 1:  #wait on job queue
            job = self.job_producer.queue.get()  #blocking wait

            if self.univ.stop_event.is_set() or job == None:  #need to stop
                _log.debug('%s received stop event' % self.name)
                break

            t = time.time()  #get the current time
            job.exec_timestamp - t > 0 and time.sleep(job.exec_timestamp - t)  #sleep till the execution time reaches
            self.job_producer.executer.add_job(job)  #add the job to executer
