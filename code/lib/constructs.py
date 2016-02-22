"""
Some useful constructs
Implements EmptyClass, SingletonType, Namespace, enum, with_static_vars, ThreadEx, EventDispatcher, NavigationDict and WorkerProcess
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import threading
import sys
import subprocess
import os
import signal
import logging

#Python 2.x vs 3.x
try:
    import queue
except ImportError:
    import Queue as queue
    
#Python 2.x vs 3.x
try:
    unicode = unicode
except:
    def unicode(object, *args, **kwargs):
        return str(object)
    
queue = queue  #export symbol queue 
_log = logging.getLogger(__name__)  #module level logging

def enum(*sequential, **named):
    """
    Function to create enumeration
    
    Returns:
        Enum type based on the sequential and named keys
    """
    
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)

def with_static_vars(**kwargs):
    """
    Decorator to initialize function level static variables
    """
    
    def decorate(func):
        for key in kwargs:
            setattr(func, key, kwargs[key])
        return func
    
    return decorate

@with_static_vars(class_counter = 1)
def singleton(*base_classes, **mappings):
    """
    Function to create singlton metaclass so that your class can inherit from it
    
    Returns:
        Unique singleton class type
    """
    
    class_name = 'SingletonMetaClass%s' % singleton.class_counter
    base_classes = base_classes or (object,)
    singleton.class_counter += 1
    return SingletonType(class_name, base_classes, mappings)

class EmptyClass:
    """
    An empty class with no attributes
    """
    
    pass

class Namespace:    
    """
    Class for creating namespaces which cannot be instantiated.
    """
    
    def __init__(self):
        """
        Constructor
        """
        
        raise RuntimeError('Cannot instantiate class')

class SingletonType(type):
    """
    Metaclass for creating singletons.
    It sores the instance in __instance attribute
    """
    
    def __call__(cls, *args, **kwargs):
        """
        Called when the instance is called as a function.
        """
        
        if hasattr(cls, '__instance') == False:  #if we dont have an instance already
            setattr(cls, '__instance', super(SingletonType, cls).__call__(*args, **kwargs))  #create the instance and store it in __instance
        elif cls is not getattr(getattr(cls, '__instance'), '__class__'):  #if the class of the instance is not the same
            setattr(cls, '__instance', super(SingletonType, cls).__call__(*args, **kwargs))  #create the instance and store it in __instance
            
        return getattr(cls, '__instance')  #return the instance

class ThreadEx(threading.Thread):
    """
    Class inherited from threading.Thread to enable exception handling.
    """
    
    def __init__(self, group = None, target = None, name = None, args = (), kwargs = {}):
        """
        Constructor
        
        Args:
            Refer threading.Thread for documentation on arguments
        """
        
        self.orig_target = target  #save the original target
        self.orig_args = args  #save the original arguments
        self.orig_kwargs = kwargs  #save the original keyword arguments
        target = self.run if target else target
        name = name if name else self.__class__.__name__
        threading.Thread.__init__(self, group, target, name)  #intialize the base class
        
    def run(self):        
        """
        Method runs in a new thread
        """
        
        try:
            _log.debug('Starting up %s' % self.name)
            (self.orig_target if self.orig_target else self.exe)(*self.orig_args, **self.orig_kwargs)  #call the target with arguments
            _log.debug('Shutting down %s' % self.name)
        except:
            #catch the exception and call sys.excepthook. we can modify sys.excepthook to save the stack trace
            type, value, tb = sys.exc_info()
            sys.excepthook(type, value, tb)
            
    def exe(self):
        """
        Thread target for the derviced class
        """
        
        pass
    
class EventDispatcher():
    """
    Event dispatcher class for cross module communication.
    """
    
    def __init__(self):
        """
        Constructor
        """
        
        self.events = {}  #dict of events. each event can have a list of callbacks
        self.lock = threading.RLock()  #locking for thread safety
        
    def bind(self, event, callback):
        """
        Public method to add a callback for an event
        
        Args:
            event: name of the event
            callback: a callable object for the event
            
        Returns:
            True if the callback is added, else False
        """
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            self.events[event] = self.events.get(event, [])  #add the event and initialize to empty callback list

            if callback not in self.events[event]:  #prevent adding same callback multiple times
                self.events[event].append(callback)
                return True
        finally:
            self.lock.release()
        
        return False
    
    def unbind(self, event, *args):
        """
        Public method to remove callbacks for an event
        If all the callbacks are removed, the event will be removed. Also if no callbacks are specified then the event is removed.
        
        Args:
            event: event name for which the callback to be removed
            
        Returns:
            callback count for the event.
        """
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            callbacks = self.events.get(event)  #get the callbacks for the event

            if callbacks == None:
                return 0

            callback_count = len(callbacks)
            args = args if len(args) else callbacks[:]  #if no callbacks specified in the function call, then remove them all

            for arg in args:
                if arg in callbacks:
                    callbacks.remove(arg)
                    callback_count -= 1

            if callback_count == 0:  #delete the event if no more callbacks remaining
                del self.events[event]
        finally:
            self.lock.release()
            
        return callback_count
    
    def trigger(self, event, *args, **kwargs):
        """
        Public method to trigger the event.
        
        Args:
            event: event name for which the callback to be removed
            
        Returns:
            callback count for the event.
        """
        
        self.lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        try:
            callbacks = self.events.get(event, [])  #get the callbacks for the event
            callback_count = 0
        
            for callback in callbacks:  #fire all the callbacks
                callback(event, *args, **kwargs)
                callback_count += 1
        finally:
            self.lock.release()
            
        return callback_count

class NavigationDict(dict):
    """
    An extended dict class that supports navigating the dict using keys.
    It is a drop in replacement for the builtin dict type
    """
    
    def get_value(self, keys):
        """
        Helper ethod to get the value from a key sequence.
        This can raise exception if key is not found
        
        Args:
            keys: list containing keys to be navigated
            
        Returns:
            Value for the key
        """
        
        data = self  #navigation starts from the root
        
        #loop through the keys supplied
        for key in keys:
            if type(data) is list:  #if the value is a list, search through that also
                #find the dict items matching the key from the list 
                items = [item[key] for item in data if type(item) is dict and item.get(key) is not None]
                length = len(items)

                if not length:  #not found
                    raise KeyError(key)

                #update the item
                data = items[0] if length == 1 else items
            else:
                data = data[key]
        
        return data
    
    def get(self, keys, default = None):
        """
        Method to get the value for a key sequence, overrides the get method of the dict
        
        Args:
            keys: a list containing the key sequence. 
                For example if dict is {'a': 'b': 'c': [{'d': 1}, {'e': 2}]}, to extract 1, the key seq should be ['a', 'b', 'c', 'd']
            default: default value to be used if the key is not found
        """
        
        if type(keys) is list:  #if the key is a list
            try:
                data = self.get_value(keys)
            except KeyError:  #catch the key error to provide the default value
                data = default
        else:  #else use the original method
            data = dict.get(self, keys, default)
        
        return data
    
    def get_dict(self, *keys, **kwargs):
        """
        Public method to return filtered dict.
        
        Args:
            keys: keys to return, specify no keys to select all keys. a key can also be tuple (key, default_value)
                A key can also be a string or a list of strings indicating the key sequence
                i.e 'key' or ('key', default) or ['key1', 'key2'] or (['key1', 'key2'], default)
            return_leaf_key: use this kw argument to alter the format of the dict returned.
                for a key sequence ['a', 'b', 'c'], True means the returned data would be {'c': value}
                False means, the data would be {'a': {'b': {'c': value}}}
            
        Returns:
            dict continaing the filtered keys
        """
        
        keys, ret, return_leaf_key = keys or list(self.keys()), {}, kwargs.get('return_leaf_key', True)
        
        def update_dict(data, keys, value):
            """
            Helper function to update the dict to be returned
            """
            
            if return_leaf_key:  #use the last key in the sequence
                data[keys[-1]] = value
            else:  #construct the whole dict
                for key in keys[:-1]:
                    data[key] = data.get(key, {})
                    data = data[key]
                    
                data[keys[-1]] = value

        for key in keys:
            #change the format of the key to tuple to consider the default vaues
            key = key if type(key) is tuple else (key,) 
            
            #current key can be a string or a list of string indicating the key sequence,
            #in any canse we should convert it to a list 
            curr_keys = key[0] if type(key[0]) is list else [key[0]]  

            try:
                update_dict(ret, curr_keys, self.get_value(curr_keys))  #update the result with the value
            except:
                if len(key) > 1:  #use the default value for the key
                    update_dict(ret, curr_keys, key[1])

        return ret
        
class WorkerProcess():
    """
    The class abstracts the (re)creation and communication with a subprocess through pipes.
    The class simply writes/reads the input/ouput to the subprocess. 
    The calling module should have an agreement with the program used to create the subprocess about the data format.
    """
    
    def __init__(self, *args):
        """
        Constructor
        
        Args:
            Command line arguments for the process
        """
        
        self.exec_process = None  #process instance
        self.process_lock = threading.RLock()  #thread lock for process instance
        self.write_count = 0  #total number of lines written to the process
        self.is_stop = False  #stop flag for the process
        self.args = list(args)  #arguments for the process
        
    def __str__(self):
        """
        String representation for the object
        
        Returns:
            A readable string representation
        """
        
        try:
            name = '%s(%d)' % (self.args[0], self.exec_process.pid)  #with pid
        except:
            name = self.args[0]
        
        return name
        
    @property
    def process(self):
        """
        Property to get the process instance
        
        Returns:
            Process instance
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        
        #self.wait returns True if the suprocess is terminated, in that case we will create a new process instance
        if self.wait() and not self.is_stop:
            try:
                self.write_count = 0  #reset the number of writes performed

                #create the process with stream handles redirected. make sure the bufsize is set to 0 to have the pipe unbuffered
                self.exec_process = subprocess.Popen(self.args, preexec_fn = self.init_process, bufsize = 0,
                    stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
                _log.info('Worker process %s has been created' % self)
            except Exception as e:
                _log.error('Failed to create %s worker process; %s' % (self, unicode(e)))
                
        self.process_lock.release()
        return self.exec_process
    
    def init_process(self):
        """
        Method to initialize the subprocess. This is called from the forked process before replacing the image
        """
        
        pass
        
    def write(self, input):
        """
        Public method to write input to the subprocess
        
        Args:
            input: input for the process.
            
        Returns:
            True on success else False
        """
        
        try:
            #it is possible that the pipe is broken or the subprocess was terminated
            self.process.stdin.write((input + '\n').encode('utf-8'))
            self.write_count += 1
        except Exception as e:
            _log.error('Failed to write to worker process %s; %s' % (self, unicode(e)))
            return False
        
        return True
        
    def read(self):
        """
        Method to read from subprocess
        
        Returns:
            The line read or None on error
        """
        
        try:
            #it is possible that the pipe is broken or the subprocess was terminated
            line = self.process.stdout.readline().decode('utf-8', 'replace').rstrip()
        except Exception as e:
            _log.error('Failed to read from worker process %s; %s' % (self, unicode(e)))
            return None
        
        return line
        
    def wait(self, is_force = False): 
        """
        Method to wait for the subprocess if it was terminated, to avoid zombies
        This method is not thread safe.
        
        Args:
            is_force: if it is True, it terminates the process and then waits
            
        Returns:
            True if the process is terminated else False
        """
        
        is_terminated = True  #is subprocess terminated
        
        try:
            if self.exec_process.poll() == None:  #if the process is running
                if is_force:  #kill the process
                    os.kill(self.exec_process.pid, signal.SIGTERM)
                else:
                    is_terminated = False  #process still running
                
            #wait for the process if it is terminated
            if is_terminated == True:
                is_force == False and _log.error('Worker process %s was terminated' % self)
                os.waitpid(self.exec_process.pid, os.WUNTRACED)
                self.exec_process = None
        except:
            pass
                
        return is_terminated
        
    def stop(self):
        """
        Public method to stop the process.
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes
        self.is_stop = True
        self.wait(True)  #terminate the subprocess and wait
        self.process_lock.release()
        
    def limit_process_usage(self, max_write_count):
        """
        Method to terminate the subprocess if it had more than N lines written to it.
        This is done to avoid memory usage in subprocess growing.
        
        Args:
            max_write_count: maximum number of lines allowed to process
        """
        
        self.process_lock.acquire()  #this has to be atomic as multiple threads reads/writes

        try:
            if self.exec_process and self.write_count > max_write_count:  #if number of commands written execeeded the maximum allowed count
                self.wait(True)
                _log.debug('Worker process %s was terminated as it processed more than %d lines' % (self, max_write_count))
        except:
            pass
  
        self.process_lock.release()
        
