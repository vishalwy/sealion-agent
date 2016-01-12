"""
Some useful constructs
Implements EmptyClass, SingletonType, Namespace, enum, with_static_vars, ThreadEx and EventDispatcher 
"""

__copyright__ = '(c) Webyog, Inc'
__author__ = 'Vishal P.R'
__email__ = 'hello@sealion.com'

import threading
import sys
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
    def get_value(self, keys):
        data = self
        
        for key in keys:
            if type(data) is list:
                items = [item[key] for item in data if type(item) is dict and item.get(key) is not None]
                length = len(items)

                if not length:
                    raise KeyError(key)

                data = items[0] if length == 1 else items
            else:
                data = data[key]
        
        return data
    
    def get(self, keys, default = None):
        if type(keys) is list:
            try:
                data = self.get_value(keys)
            except KeyError:
                data = default
        else:
            data = dict.get(self, keys, default)
        
        return data
    
    def get_dict(self, *keys, **kwargs):
        """
        Public method to return filtered dict.
        
        Args:
            keys: keys to return, specify no keys to select all keys. a key can also be tuple (key, default_value)
            
        Returns:
            dict continaing the filtered keys
        """
        
        keys, ret, return_leaf_key = keys or list(self.keys()), {}, kwargs.get('return_leaf_key', True)
        
        def update_dict(data, keys, value):
            if return_leaf_key:
                data[keys[-1]] = value
            else:
                for key in keys[:-1]:
                    data[key] = data.get(key, {})
                    data = data[key]
                    
                data[keys[-1]] = value
        
        for key in keys:
            key = key if type(key) is tuple else (key,)  #get the key
            curr_keys = key[0] if type(key[0]) is list else [key[0]]
            
            try:
                update_dict(ret, curr_keys, self.get_value(curr_keys))
            except:
                if len(key) > 1:  #use the default value for the key
                    update_dict(ret, curr_keys, key[1])

        return ret
        
        
