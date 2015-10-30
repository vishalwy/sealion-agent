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
import sys
import universal
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
    
class Job:    
    """
    Represents a job, that can be executed
    """
    
    def __init__(self, activity):
        """
        Constructor
        
        Args:
            activity: dict representing the activity to be executed
        """
        
        self.is_whitelisted = activity['is_whitelisted']  #is this job allowed to execute
        self.exec_timestamp = activity['next_exec_timestamp']  #timestamp at which the job should execute
        self.status = JobStatus.INITIALIZED  #current job state
        self.is_plugin = True if activity['details'].get('service') == 'Plugins' else False  #is this job a plugin or a commandline
        
        #dict containing job execution details
        self.exec_details = {
            'timestamp': 0,  #actual timestamp when the job started
            'output': None,  #output of the job, file handle for commandline job, dict for successful pugin execution, str for failed pugin execution. 
            'pid': -1,  #process id if it is a commandline job
            'return_code': 0,  #return code of the job
            '_id': activity['details']['_id'],  #activity id
            'command': activity['details']['command']  #command to be executed for commandline job, else the python module name for plugin job
        }
        
        self.univ = universal.Universal()  #reference to Universal for optimized access

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
                self.exec_details['output'] = '%d' % t
                
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

        if self.status == JobStatus.RUNNING and not self.is_plugin and self.exec_details['pid'] == -1:  #commandline job who's pid is unknown
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
                #we supply the instance method to read the output on demand
                #this reduces the memory used unneceserily reading the output and putting it in the queue
                data['data'] = self.read_output
        else:
            format = 'No data for activity (%(activity)s @ %(timestamp)d); satus: %(status)d; pid: %(pid)d; output: %(output)s'
            format_spec = {
                'activity': self.exec_details['_id'],
                'timestamp': self.exec_details['timestamp'],
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
            Output read.
        """
        
        try:
            #for a commandline job, output is the file containing data
            output_file = open('%s/%s' % (self.univ.temp_path, self.exec_details['output']), 'rb')
            data = output_file.read(256 * 1024).decode('utf-8', 'replace')
            output_file.close()

            if not data:  #if the file is empty
                data = 'No output produced'
                _log.debug('No output/error found for activity (%s @ %d)' % (self.exec_details['_id'], self.exec_details['timestamp']))
                
            _log.debug('Read output from activity (%s @ %d)' % (self.exec_details['_id'], self.exec_details['timestamp']))
        except Exception as e:
            data = ''
            _log.error('Could not read output from activity (%s @ %d); %s' % (self.exec_details['_id'], self.exec_details['timestamp'], unicode(e)))
            
        self.remove_file()  #remove the output file
        return data

    def remove_file(self):
        """
        Public method to delete output file if any
        """
        
        try:
            #it is possible that output is not a file, in that case it will raise an exception which is ignored
            os.remove('%s/%s' % (self.univ.temp_path, self.exec_details['output']))
            _log.debug('Removed the output file for activity (%s @ %d)' % (self.exec_details['_id'], self.exec_details['timestamp']))
        except:
            pass
        
        self.exec_details['output'] = None
    
class Executer(ThreadEx):
    """
    A wrapper class that creates a bash subprocess for commandline job execution
    It executes the commandline by writing to the bash script and gets the status in a blocking read.
    For more details checkout execute.sh
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
        self.exec_count = 0  #total number of commands executed in the bash process
        self.is_stop = False  #stop flag for the thread
        self.univ = universal.Universal()  #reference to Universal for optimized access
        self.daemon = True  #run this thread as daemon as it should not block agent from shutting down
        self.univ.event_dispatcher.bind('terminate', self.stop)  #bind to terminate event so that we can terminate bash process
        self.env_variables = {}  #env variables received from the server to execute commands
        
        #use the job timeout defined in the config if we have one
        try:
            self.timeout = self.univ.config.sealion.commandTimeout
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
            self.write(job.exec_details)
        else:            
            try:
                #we load the plugin and calls the get_data function and updates the job with the data
                #this can raise exception
                plugin = __import__(job.exec_details['command'])
                job.update({'return_code': 0, 'output': plugin.get_data()})
            except Exception as e:
                #on failure we set the status code as ignored, so that output is not processed
                job.status = JobStatus.IGNORED
                _log.error('Failed to get data for plugin activity (%s @ %d); %s' % (job.exec_details['_id'], job.exec_details['timestamp'], unicode(e)))
        
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
            
            #if the job exceeds the timeout
            if job.status == JobStatus.RUNNING and t - job.exec_details['timestamp'] > self.timeout:
                job.kill() and _log.info('Killed activity (%s @ %d) as it exceeded timeout' % (job.exec_details['_id'], job.exec_details['timestamp']))

            if job.status == JobStatus.IGNORED:  #remove the job if it is to be ignored
                del Executer.jobs[job_timestamp]
            elif job.status != JobStatus.RUNNING:  #collect the job if it is not running and remove it from the dict
                finished_jobs.append(job)
                del Executer.jobs[job_timestamp]
                
        not finished_jobs and not Executer.jobs and self.limit_process_usage()
        Executer.jobs_lock.release()
        finished_jobs and _log.info('Finished execution of %d activities' % len(finished_jobs))
        return finished_jobs
    
    def limit_process_usage(self):
        """
        Method to terminate the bash subprocess if it has executed more than a N commands.
        This is done to avoid memory usage in bash subprocess growing.
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes

        try:
            max_exec_count = 2222;  #maximum count of commands allowed in the bash process

            if self.exec_process and self.exec_count > max_exec_count:  #if number of commands executed execeeded the maximum allowed count
                _log.debug('Terminatng bash process %d as it executed more than %d commands' % (self.exec_process.pid, max_exec_count))
                self.wait(True)
        finally:    
            self.process_lock.release()
        
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
                
    @property
    def process(self):
        """
        Property to get the bash process instance
        
        Returns:
            Bash process instance
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        #self.wait returns True if the bash suprocess is terminated, in that case we will create a new bash process instance
        if self.wait() and not self.is_stop:
            try:
                #refer execute.sh to read more about arguments to be passed in 
                exec_args = ['bash', '%s/src/execute.sh' % self.univ.exe_path, self.univ.main_script]
                os.isatty(sys.stdin.fileno()) or exec_args.append('1')

                #collect env variables for command line execution.
                #env variables defined in sealion config takes precedence over the ones in agent config
                env_vars = dict(os.environ)
                env_vars.update(self.env_variables)
                env_vars.update(self.univ.config.sealion.get_dict(('env', {}))['env'])

                self.exec_count = 0  #reset the number of commands executed

                self.exec_process = subprocess.Popen(exec_args, preexec_fn = self.init_process, bufsize = 0, env = env_vars,
                    stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
                _log.info('Bash process %d has been created to execute command line activities' % self.exec_process.pid)
            except Exception as e:
                _log.error('Failed to create bash process; %s' % unicode(e))
                
        self.process_lock.release()
        return self.exec_process
    
    @staticmethod
    def format_job(job_details):
        """
        Method to get the formated string representing the commandline job
        
        Args:
            job_details: dict representing the commandline job to be stringified
            
        Returns:
            String representing the job
        """
        
        return ('%d %s: %s\n' % (job_details['timestamp'], job_details['output'], job_details['command'])).encode('utf-8')
    
    def write(self, job_details):
        """
        Public method to write the commandline job to the bash subprocess
        
        Args:
            job_details: dict representing the commandline job to be executed; this can also be a maintainance command.
            
        Returns:
            True on success else False
        """
        
        try:
            #it is possible that the pipe is broken or the subprocess was terminated
            self.process.stdin.write(Executer.format_job(job_details))
            self.exec_count += 1
        except Exception as e:
            _log.error('Failed to write to bash process; %s' % unicode(e))
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
            line = self.process.stdout.readline().decode('utf-8', 'replace').rstrip()
            data = line.split()
            
            if not data:  #bash wrote an empty line; ignore it
                return False
            elif data[0] == 'warning:':  #bash has given some warning
                _log.warn(line[line.find(' ') + 1:])
            elif data[0] == 'data:':  #data
                self.update_job(int(data[1]), {data[2]: data[3]})
            else:  #everything else
                _log.info('Bash process returned \'%s\'' % line)
        except Exception as e:
            _log.error('Failed to read from bash process; %s' % unicode(e))
            return False
        
        return True
        
    def wait(self, is_force = False): 
        """
        Method to wait for the bash subprocess if it was terminated, to avoid zombies
        This method is not thread safe.
        
        Args:
            is_force: if it is True, it terminates the process and then waits
            
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
                is_force == False and _log.error('Bash process %d was terminated', self.exec_process.pid)
                os.waitpid(self.exec_process.pid, os.WUNTRACED)
                self.exec_process = None
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
        env_vars = self.univ.config.agent.get_dict(('envVariables', {}))['envVariables']
        job_details = {'timestamp': 0, 'output': '/dev/stdout', 'command': 'export %s=\'%s\''}  #maintainance job
        
        #this has to be atomic as we want to update the env variables before executing the next job
        self.process_lock.acquire()  
        
        for env_var in env_vars:
            value = env_vars[env_var] 
            set_vars.append(env_var)
            
            if value == self.env_variables.get(env_var):
                continue
            
            try:
                #update the env variable and export it to the curent bash process
                self.env_variables[env_var] = value
                job_details['command'] = 'export %s=\'%s\'' % (env_var, value.replace('\'', '\'\\\'\''))
                self.exec_process and self.exec_process.stdin.write(Executer.format_job(job_details))
                export_count += 1
                _log.info('Exported env variable %s' % env_var)
            except Exception as e:
                _log.error('Failed to export env variable %s; %s' % (env_var, unicode(e)))
            
        #find any env vars in the dict that is not in the set variables list and delete
        for env_var in [env_var for env_var in self.env_variables if env_var not in set_vars]:
            try:
                #delete the env variable and unset it from the curent bash process
                del self.env_variables[env_var]
                job_details['command'] = 'unset %s' % env_var
                self.exec_process and self.exec_process.stdin.write(Executer.format_job(job_details))
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
        
        whitelist, command = [], activity['command']
        
        if activity.get('service') == 'Plugins':  #always execute plugin activities
            return True

        if hasattr(self.univ.config.sealion, 'whitelist'):  #read the whitelist from config
            whitelist = self.univ.config.sealion.whitelist
            
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
        
    def set_activities(self):
        """
        Method updates the dict containing the activities.
        
        Returns:
            Tuple containing (total_count, plugin_count, start_count, update_count, stop_count)
        """
        
        activities = self.univ.config.agent.activities
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
                    _log.info('Updatied activity %s' % activity_id)
                    update_count += 1
            else:
                #add a new activity
                self.activities[activity_id] = {
                    'details': activity,
                    'is_whitelisted': self.is_in_whitelist(activity),  #check whether the activity is allowed to run
                    'next_exec_timestamp': t  #execute the activity immediately
                }
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
        self.executer.stop()  #stop executer for suprocess
        
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
