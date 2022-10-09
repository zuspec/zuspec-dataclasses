'''
Created on Mar 19, 2022

@author: mballance
'''

import vsc_dataclasses.impl as vsc_impl

from .context import FlowObjKindE
from .ctor import Ctor
from .struct_kind_e import StructKindE
from .base_decorator_impl import BaseDecoratorImpl
from .type_kind_e import TypeKindE
from .exec_kind_e import ExecKindE
from .typeinfo_struct import TypeInfoStruct

class StructDecoratorImpl(BaseDecoratorImpl):
    
    def __init__(self, kind, args, kwargs):
        super().__init__(args, kwargs)
        self._kind = kind

    def get_type_category(self):
        return self._kind

    def pre_decorate(self, T):
        struct_ti = TypeInfoStruct.get(self.get_typeinfo())
        struct_ti._kind = self._kind
        print("struct_ti: %s" % str(struct_ti))

        if self._kind == StructKindE.Resource:
            # Add in built-in 'instance_id' field
            inst_id_fi = vsc_impl.TypeInfoField("instance_id", vsc_impl.TypeInfoScalar(False))
            struct_ti.addField(inst_id_fi, None)


        super().pre_decorate(T)
        
    def _validateExec(self, kind):
        return kind in [ExecKindE.PreSolve, ExecKindE.PostSolve]
    
    def _getLibDataType(self, name):
        kind_m = {
            StructKindE.Buffer : FlowObjKindE.Buffer,
            StructKindE.Resource : FlowObjKindE.Resource,
            StructKindE.State : FlowObjKindE.State,
            StructKindE.Stream : FlowObjKindE.Stream
        }
        ctor_a = Ctor.inst()

        ds_t = ctor_a.ctxt().findDataTypeFlowObj(name, kind_m[self._kind])
        
        if ds_t is None:
            ds_t = ctor_a.ctxt().mkDataTypeFlowObj(name, kind_m[self._kind])
            ctor_a.ctxt().addDataTypeFlowObj(ds_t)

        return ds_t
