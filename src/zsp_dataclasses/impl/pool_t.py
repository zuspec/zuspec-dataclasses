'''
Created on May 12, 2022

@author: mballance
'''
from .pool_meta_sz_t import PoolMetaSzT
from .pool_size import PoolSize
from .field_pool_impl import FieldPoolImpl
from .ctor import Ctor
from .ctor_scope import CtorScope

class PoolT(metaclass=PoolMetaSzT):
    T = None
    SZ = -1
    
    def __init__(self, *args, **kwargs):
        raise Exception("Pool types may not be created explicitly")

    @classmethod
    def createField(cls, name):
        ctor = Ctor.inst()
        s : CtorScope = ctor.scope()
        ret = FieldPoolImpl(
            name,
            s.lib_scope,
            cls.T._typeinfo)
        
        return ret

    