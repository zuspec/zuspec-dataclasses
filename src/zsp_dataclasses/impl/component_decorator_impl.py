'''
Created on Mar 19, 2022

@author: mballance
'''

import typeworks
import vsc_dataclasses.impl as vsc_impl
import vsc_dataclasses.impl.context as vsc_ctxt
from .bind_all_impl import BindAllImpl
from .context import PoolBindKind

from .pool_meta_sz_t import PoolMetaSzT

from .pool_t import PoolT
from .typeinfo_pool import TypeInfoPool
from .typeinfo_flow_obj import TypeInfoFlowObj
from .base_decorator_impl import BaseDecoratorImpl
from .type_info import TypeInfo
from .type_kind_e import TypeKindE
from .decorator_impl_base import DecoratorImplBase
from .component_impl import ComponentImpl
from .exec_kind_e import ExecKindE
from .ctor import Ctor
from .type_kind_e import TypeKindE
from .typeinfo_action import TypeInfoAction
from .typeinfo_component import TypeInfoComponent


class ComponentDecoratorImpl(BaseDecoratorImpl):

    IllegalTypeInfo = (
        TypeInfoAction,
        TypeInfoFlowObj
    )

    def get_type_category(self):
        return TypeKindE.Component

    def _getLibDataType(self, name):
        ctor = Ctor.inst()
        ds_t = ctor.ctxt().findDataTypeComponent(name)
        
        if ds_t is None:
            ds_t = ctor.ctxt().mkDataTypeComponent(name)
            ctor.ctxt().addDataTypeComponent(ds_t)

            if ctor.ctxt().findDataTypeComponent(name) is None:
                raise Exception("It's None Jim")
        else:
            raise Exception("Type %s is already registered" % name)

        print("Create Component datatype %s" % name)
        
        return ds_t

    def pre_decorate(self, T):
        component_ti = TypeInfoComponent.get(self.get_typeinfo())

        super().pre_decorate(T)

        # Collect action declarations and elaborate
        # Note: lib_typeobj for this component will not be valid 
        # until after the super executes
        for action_ti in typeworks.DeclRgy.pop_decl(TypeInfoAction):
            component_ti.addActionT(action_ti)

    def init_annotated_field(self, key, value, has_init, init):
        component_ti = TypeInfoComponent.get(self.get_typeinfo())
        value_ti = typeworks.TypeInfo.get(value, False)

        print("init_annotated_field: %s %s" % (key, str(value)))

        if issubclass(value, (PoolT,PoolMetaSzT)):
            ctor_a = Ctor.inst()
            print("is pool")
            ctor = vsc_impl.Ctor.inst()
            # TODO: extract typeinfo for field type
            pool_t_ti = typeworks.TypeInfo.get(value.T, False)
            if pool_t_ti is None:
                raise Exception("Type %s is not registered" % (value.T))
            pool_t_base_ti = TypeInfo.get(pool_t_ti, False)

            pool_fi = TypeInfoPool(key, pool_t_base_ti)
            pool_obj = ctor_a.ctxt().mkTypeFieldPool(
                            key,
                            pool_t_base_ti.lib_typeobj,
                            False,
                            vsc_ctxt.TypeFieldAttr.NoAttr,
                            value.SZ)
            component_ti.addField(pool_fi, pool_obj) 

            if has_init:
                if isinstance(init, BindAllImpl):
                    print("Have bind-all")
                    pool_ref = ctor_a.ctxt().mkTypeExprFieldRef()
                    pool_ref.addIdxRef(pool_fi.idx)
                    pool_ref.addRootRef()
                    component_ti.lib_typeobj.addPoolBindDirective(
                        ctor_a.ctxt().mkPoolBindDirective(
                            PoolBindKind.All,
                            pool_ref,
                            None))
            else:
                self.set_field_initial(key, None)
        elif value_ti is not None:
            # TODO: catch fields of component type (?)
            value_base_ti = TypeInfo.get(value_ti, False)

            if value_base_ti is not None:
                if isinstance(value_base_ti, TypeInfoComponent):
                    ctor = vsc_impl.Ctor.inst()

                    comp_obj = ctor.ctxt().mkTypeFieldPhy(
                            key,
                            value_base_ti.lib_typeobj,
                            False,
                            vsc_ctxt.TypeFieldAttr.NoAttr,
                            None)
                    comp_fi = vsc_impl.TypeInfoField(key, value_base_ti)
                    component_ti.addField(comp_fi, comp_obj)
                    self.set_field_initial(key, None)
                elif isinstance(value_base_ti, ComponentDecoratorImpl.IllegalTypeInfo):
                    raise Exception("illegal component field kind: %s" % str(value_base_ti))
                else:
                    super().init_annotated_field(key, value, has_init, init)
            else:
                super().init_annotated_field(key, value, has_init, init)
        else:
            super().init_annotated_field(key, value, has_init, init)

    def post_decorate(self, T, Tp):
        component_ti = TypeInfoComponent.get(self.get_typeinfo())
        super().post_decorate(T, Tp)

        # Add component-specific methods and remove irrelevant ones
        ComponentImpl.addMethods(Tp)

    def pre_register(self):
        component_ti = TypeInfoComponent.get(self.get_typeinfo())

        super().pre_register()

    def elab_type(self):
        component_ti = TypeInfoComponent.get(self.get_typeinfo())
        component_ti.elab_obj_ctor = lambda obj=self: obj.create_type_inst()
    
    def _validateExec(self, kind):
        return kind in (ExecKindE.InitDown, ExecKindE.InitUp)
    

