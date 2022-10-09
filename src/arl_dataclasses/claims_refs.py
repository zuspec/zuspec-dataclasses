'''
Created on Mar 19, 2022

@author: mballance
'''
from .impl.input_meta_t import InputMetaT
from .impl.output_meta_t import OutputMetaT
from .impl.lock_meta_t import LockMetaT
from .impl.share_meta_t import ShareMetaT
from .impl.pool_meta_t import PoolMetaT


class input(metaclass=InputMetaT):
    pass

class output(metaclass=OutputMetaT):
    pass

class lock(metaclass=LockMetaT):
    pass

class share(metaclass=ShareMetaT):
    pass

class pool(metaclass=PoolMetaT):
    pass