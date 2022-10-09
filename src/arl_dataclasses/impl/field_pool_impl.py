'''
Created on May 12, 2022

@author: mballance
'''

import vsc_dataclasses.impl as vsc_impl
from .ctor import Ctor
from .struct_kind_e import StructKindE

class FieldPoolImpl(vsc_impl.FieldBaseImpl):
    
    def __init__(self, name, typeinfo, idx):
        super().__init__(name, typeinfo, idx)

    @property
    def size(self):
        if self._modelinfo._typeinfo._kind != StructKindE.Resource:
            raise Exception("Size is only valid on resource pools. Pool %s is of kind %s" % (
                self.name, self._modelinfo._typeinfo._kind))
        else:
            return self._modelinfo.libobj.getField(0).val().val_i()
    
    @size.setter
    def size(self, v):
        ctor = Ctor.inst()
        
        if ctor.is_type_mode():
            raise Exception("Attempting to set size in type mode")
        else:
            if self._modelinfo._typeinfo._kind != StructKindE.Resource:
                raise Exception("Size can only be specified on resource pools. Pool %s is of kind %s" % (
                    self._modelinfo.name, self._modelinfo._typeinfo._kind))
            print("Set value to %d" % v)
            self._modelinfo.libobj.getField(0).val().set_val_i(v)
