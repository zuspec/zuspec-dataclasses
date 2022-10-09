'''
Created on May 12, 2022

@author: mballance
'''
from .pool_t import PoolT
from .pool_size import PoolSize

class PoolMetaT(type):
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        if item in self.type_m.keys():
            return self.type_m[item]
        else:
            t = type("pool_t[%s]" % item.__qualname__, (PoolT,), {})
            print("Creating pool-type %s" % str(t))
            t.T = item
            self.type_m[item] = t
            return t
        
#    def size(self, sz):
#        return PoolSize(sz)