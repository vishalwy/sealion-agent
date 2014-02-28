import threading
import sys

try:
    import queue as t
except ImportError:
    import Queue as t
    
queue = t

class EmptyClass:
    pass

class SingletonType(type):
    def __call__(cls, *args, **kwargs):
        if hasattr(cls, '__instance') == False:
            setattr(cls, '__instance', super(SingletonType, cls).__call__(*args, **kwargs))
        elif cls is not getattr(getattr(cls, '__instance'), '__class__'):
            setattr(cls, '__instance', super(SingletonType, cls).__call__(*args, **kwargs))
            
        return getattr(cls, '__instance')
    
class Namespace:    
    def __init__(self):
        raise RuntimeError('Cannot instantiate class')
    
class DictEx(dict):
    def __init__(self, *args, **kwargs):
        super(DictEx, self).__init__(*args, **kwargs)
    
    def get_dict(self, keys = None, as_dict = True):
        ret = {} if as_dict else DictEx()
        
        if keys == None:
            keys = zip(self.keys())
        
        for i in range(0, len(keys)):
            is_tuple = True if type(keys[i]) is tuple else False
            key = keys[i][0] if is_tuple else keys[i]
            
            if (key in self):
                ret[key] = self[key]
            elif is_tuple and len(keys[i]) > 1:
                ret[key] = keys[i][1]
                
        return ret
    
def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)

class ThreadEx(threading.Thread):
    def __init__(self, group = None, target = None, name = None, args = (), kwargs = {}):
        self.orig_target = target
        self.orig_args = args
        self.orig_kwargs = kwargs
        target = self.run if target else target
        threading.Thread.__init__(self, group, target, name)
        
    def run(self):        
        try:
            (self.orig_target if self.orig_target else self.exe)(*self.orig_args, **self.orig_kwargs)
        except:
            type, value, tb = sys.exc_info()
            sys.excepthook(type, value, tb)
            
    def exe(self):
        pass
    
class EventDispatcher():
    def __init__(self):
        self.events = {}
        
    def bind(self, event, callback):
        self.events[event] = self.events.get(event, [])
        
        if (callback in self.events[event]) == False:
            self.events[event].append(callback)
            return True
        
        return False
    
    def unbind(self, event, *args):
        callbacks = self.events.get(event)
        
        if callbacks == None:
            return 0
        
        callback_count = len(callbacks)
        
        for arg in args:
            if arg in callbacks:
                callbacks.remove(arg)
                callback_count -= 1
                
        if callback_count == 0: 
            del self.events[event]
            
        return callback_count
    
    def trigger(self, event, *args, **kwargs):
        callbacks = self.events.get(event, [])
        callback_count = 0
        
        for callback in callbacks:
            callback(event, *args, **kwargs)
            callback_count += 1
            
        return callback_count

    