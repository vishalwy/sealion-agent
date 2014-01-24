import os.path
import json
import os
from constructs import *

class OfflineStore:
    __metaclass__ = SingletonType
    
    def __init__(self, path):
        self.path = path
        self.files = []
        pass
    
    def put(self, activity, data):
        file_name = activity + '_' + data.timestamp + '.json'
        file_name = self.path + file_name
        
        try:
            f = open(file_name, 'w')
            json.dump(data, f)
            f.close()
            return True
        except:
            return False        
            
    def get_files(self): 
        if len(self.files):
            return self.files
        
        files = os.listdir(self.path);
        i = len(files) - 1
        
        while i >= 0:
            if os.path.isfile(self.path + files[i]) == False:
                files.pop(i)
            
            i -= 1
            
        self.files = sorted(files, key = lambda file: os.stat(file).st_ctime)
    
    def get(self):
        self.get_files()
        return self.files.pop(0) if len(self.files) else None
    
    