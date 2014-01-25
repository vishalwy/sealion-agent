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
        raise RuntimeError, 'Cannot instantiate class'
    
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
            
            if self.has_key(key):
                ret[key] = self[key]
            elif is_tuple and len(keys[i]) > 1:
                ret[key] = keys[i][1]
                
        return ret
    
def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)