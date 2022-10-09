'''
Created on Mar 19, 2022

@author: mballance
'''
from .ctor import Ctor
from .ctor_scope import CtorScope
from .field_claim_impl import FieldClaimImpl


class InputOutputT(object):
    T = None
    IsInput = True
    
    @classmethod
    def createField(cls, name):
        ctor = Ctor.inst()
        s : CtorScope = ctor.scope()
        ret = FieldClaimImpl(
            name,
            s.lib_scope,
            cls.T._typeinfo)
    