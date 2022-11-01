'''
Created on Mar 19, 2022

@author: mballance
'''

import vsc_dataclasses.impl as vsc_impl
import vsc_dataclasses.impl.context as vsc_ctxt
import typeworks

from .input_output_t import InputOutputT
from .lock_share_t import LockShareT

from .activity_decl import ActivityDecl

from .base_decorator_impl import BaseDecoratorImpl
from .typeinfo_comp_ref import TypeInfoCompRef
from .impl_base import ImplBase
from .action_decl import ActionDecl
from .type_info import TypeInfo
from .type_kind_e import TypeKindE
from .decorator_impl_base import DecoratorImplBase
from .action_impl import ActionImpl
from .exec_kind_e import ExecKindE
from .ctor import Ctor
from .typeinfo_action import TypeInfoAction

class ActionDecoratorImpl(BaseDecoratorImpl):

    def get_type_category(self):
        return TypeKindE.Action

    def pre_decorate(self, T):
        print("Action.pre_decorate")
        action_ti : TypeInfoAction = TypeInfoAction.get(self.get_typeinfo())
        ctor_a = Ctor.inst()

        for activity_t in typeworks.DeclRgy.pop_decl(ActivityDecl, typeworks.scopename(T)):
            print("activity: %s" % str(activity_t))
            action_ti.addActivity(activity_t)

        super().pre_decorate(T)

        # Add a Python reprensentation of the 'comp' reference field
        comp_fi = vsc_impl.TypeInfoField("comp", TypeInfoCompRef())
        action_ti.addField(comp_fi, None)

    def init_annotated_field(self, key, value, has_init, init):
        action_ti : TypeInfoAction = TypeInfoAction.get(self.get_typeinfo())
        ctor_a = Ctor.inst()
        # TODO: we must recognize claims, refs, and actions

        print("value: %s" % str(value))
        ti = typeworks.TypeInfo.get(value)

        if issubclass(value, (InputOutputT,LockShareT)):
            print("Ref or Claim")
            obj_t_ti = typeworks.TypeInfo.get(value.T, False)
            if obj_t_ti is None:
                raise Exception("Type %s is not registered" % str(value.T))
            
            obj_t_base_ti = TypeInfo.get(obj_t_ti, False)

            if issubclass(value, InputOutputT):
                field_obj = ctor_a.ctxt().mkTypeFieldInOut(
                    key,
                    obj_t_base_ti.lib_typeobj,
                    value.IsInput)
            else:
                field_obj = ctor_a.ctxt().mkTypeFieldClaim(
                    key,
                    obj_t_base_ti.lib_typeobj,
                    value.IsLock)

            field_ti = vsc_impl.TypeInfoField(key, vsc_impl.TypeInfoRef(obj_t_base_ti))
            action_ti.addField(field_ti, field_obj)
            self.set_field_initial(key, None)
        elif ti is not None:
            print("ti is not None")
            ti_a = TypeInfo.get(ti, True)
            print("ti_a=%s" % str(ti_a))
            if ti_a is not None:
                if isinstance(ti_a, TypeInfoAction):
                    print("Action: lib_typeobj=%s" % str(ti_a.lib_typeobj))
                    field_obj = ctor_a.ctxt().mkTypeFieldPhy(
                            key,
                            ti_a.lib_typeobj,
                            False,
                            vsc_ctxt.TypeFieldAttr.NoAttr,
                            None)
                    field_ti = vsc_impl.TypeInfoField(key, ti_a)
                    action_ti.addField(field_ti, field_obj)
                    self.set_field_initial(key, None) # Ensure dataclasses doesn't add a ctor arg
                else:
                    super().init_annotated_field(key, value, has_init, init)
            else:
                super().init_annotated_field(key, value, has_init, init)
        else:
            super().init_annotated_field(key, value, has_init, init)

    def post_decorate(self, T, Tp):
        super().post_decorate(T, Tp)

        typeworks.DeclRgy.add_inner_type(Tp)

        # Add specific methods
        ActionImpl.addMethods(Tp)

    def pre_register(self):
        print("Action.pre_register")
        action_ti = TypeInfoAction.get(self.get_typeinfo())
        typeworks.DeclRgy.push_decl(
            TypeInfoAction, 
            action_ti, 
            typeworks.enclosing_scopename(self.T))


        super().pre_register()

    def elab_type(self):
        # Elaboration for actions is deferred until the component
        # is declared
        action_ti = TypeInfoAction.get(self.get_typeinfo())
        action_ti.elab_obj_ctor = lambda obj=self: obj.create_type_inst()

    def _mkTypeInfo(self, Tp, kind : TypeKindE):
        return TypeInfoAction(Tp)
   
    def _getLibDataType(self, name):
        ctor = Ctor.inst()
        print("Action name: %s" % name)
        ds_t = ctor.ctxt().findDataTypeAction(name)
        if ds_t is None:
            ds_t = ctor.ctxt().mkDataTypeAction(name)
#            ds_t.setCreateHook(lambda obj: ActionImpl._createHook(self.T, obj))
            ctor.ctxt().addDataTypeAction(ds_t)
        return ds_t

