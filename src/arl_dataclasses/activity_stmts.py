'''
Created on Mar 19, 2022

@author: mballance
'''
from .impl.activity_sequence_meta_t import ActivitySequenceMetaT
from .impl.do_impl import DoImpl
from .impl.activity_parallel_impl import ActivityParallelImpl
from .impl.activity_parallel_meta_t import ActivityParallelMetaT
from .impl.activity_replicate_impl import ActivityReplicateImpl
from .impl.activity_sequence_impl import ActivitySequenceImpl

from .impl.activity_block_meta_t import ActivityBlockMetaT
from .impl.do_impl_meta import DoImplMeta


class parallel(ActivityParallelImpl, metaclass=ActivityParallelMetaT):
    pass

class replicate(ActivityReplicateImpl):
    pass

class sequence(ActivitySequenceImpl,metaclass=ActivitySequenceMetaT):
    pass
    
class schedule(metaclass=ActivityBlockMetaT):
    def __init__(self, *args, **kwargs):
        pass
    
    def __enter__(self):
        print("sequence.__enter__")
        
    def __exit__(self, t, v, tb):
        pass

class match(object):
    
    def __init__(self, expr):
        pass
    
    def __enter__(self):
        print("sequence.__enter__")
        
    def __exit__(self, t, v, tb):
        pass

class do(DoImpl,metaclass=DoImplMeta):
    pass
