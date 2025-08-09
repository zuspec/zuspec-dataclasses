'''
Created on May 13, 2022

@author: mballance
'''
import vsc_dataclasses.impl as vsc_impl


class FieldClaimImpl(object):
    
    def __init__(self, name, lib_field, typeinfo):
        self._modelinfo = vsc_impl.ModelInfo(self, name)
        self._modelinfo._lib_obj = lib_field
        self._modelinfo._typeinfo = typeinfo
        
    