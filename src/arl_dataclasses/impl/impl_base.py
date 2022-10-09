'''
Created on Apr 4, 2022

@author: mballance
'''
import typeworks
import vsc_dataclasses.impl as vsc_impl
from .ctor import Ctor
from .exec_group import ExecGroup
from .exec_kind_e import ExecKindE
from .rt_ctxt import RtCtxt
from .type_info import TypeInfo

class ImplBase(object):
    
    @staticmethod
    def setattr(self, name, v):
        try:
            fo = object.__getattribute__(self, name)
        except:
            object.__setattr__(self, name, v)
        else:
            object.__setattr__(self, name, v)
            
    @staticmethod
    def getattribute(self, name):
        ctor = Ctor.inst()
        ret = object.__getattribute__(self, name)
        
        if not ctor.expr_mode():
            # TODO: Check whether this is a 'special' field
            if hasattr(ret, "get_val"):
                ret = ret.get_val()
        
        return ret
    
    @staticmethod
    def _evalExecSolve(self, kind):
        typeinfo = typeworks.TypeInfo.get(type(self))
        base_ti = TypeInfo.get(typeinfo)
        
        if kind in typeinfo._exec_m.keys():
            self._evalExecSolveGroup(typeinfo._exec_m[kind])
            
    @staticmethod            
    async def _evalExecSolveGroup(self, group):
        RtCtxt.inst().push_exec_group(group)
        if hasattr(self, "super"):
            ex_super = getattr(self, "super")
        else:
            ex_super = None
        
        setattr(self, "super", self._execSuperSolve)

        for e in group._exec_l:
            e.func(self)
            
        # Restore super                
        if ex_super is not None:
            setattr(self, "super", ex_super)
        else:
            delattr(self, "super")
        RtCtxt.inst().pop_exec_group()
    
    @staticmethod
    async def _evalExecTarget(self, kind : ExecKindE):
        typeinfo = TypeInfo.get(typeworks.TypeInfo.get(type(self)))
        print("_evalExecTarget: type=%s typeinfo=%s" % (
            str(type(self)), str(typeinfo)), flush=True)

        if kind in typeinfo._exec_m.keys():
            await self._evalExecTargetGroup(typeinfo._exec_m[kind])

    @staticmethod            
    async def _evalExecTargetGroup(self, group : ExecGroup):
        RtCtxt.inst().push_exec_group(group)
        if hasattr(self, "super"):
            ex_super = getattr(self, "super")
        else:
            ex_super = None
        
        setattr(self, "super", self._execSuperTarget)

        for e in group._exec_l:
            await e.func(self)
            
        # Restore super                
        if ex_super is not None:
            setattr(self, "super", ex_super)        
        else:
            delattr(self, "super")
        RtCtxt.inst().pop_exec_group()

    def _execSuperSolve(self):
        group = RtCtxt.inst().exec_group()

        if group._super is not None:
            self._evalExecSolveGroup(group._super)        
    
    async def _execSuperTarget(self):
        group = RtCtxt.inst().exec_group()

        if group._super is not None:
            await self._evalExecTargetGroup(group._super)

    @classmethod
    def addMethods(cls, T):
        setattr(T, "__repr__", vsc_impl.RandClassImpl.__repr__)
        setattr(T, "__setattr__", vsc_impl.RandClassImpl.__setattr__)
        setattr(T, "__getattribute__", vsc_impl.RandClassImpl.__getattribute__)
#        setattr(T, "get_val", vsc_impl.RandClassImpl.get_val)
        setattr(T, "_evalExecSolve", ImplBase._evalExecSolve)
        setattr(T, "_evalExecTarget", ImplBase._evalExecTarget)
        setattr(T, "_evalExecTargetGroup", ImplBase._evalExecTargetGroup)
        setattr(T, "_execSuperSolve", ImplBase._execSuperSolve)
        setattr(T, "_execSuperTarget", ImplBase._execSuperTarget)
    pass
