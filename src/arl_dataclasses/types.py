'''
Created on Apr 26, 2022

@author: mballance
'''

# Bring in the VSC types as RG types
from vsc_dataclasses.types import *

from .impl.bind_all_impl import BindAllImpl
from .impl.pool_meta_t import PoolMetaT

#class pool(metaclass=PoolMetaT):
#    pass

def bind_all():
    """Initiatlizer for a pool with a wildcard bind"""
    return BindAllImpl()

