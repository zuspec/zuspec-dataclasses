'''
Created on Apr 4, 2022

@author: mballance
'''

import typeworks
import vsc_dataclasses.impl as vsc_impl

from .typeinfo_action import TypeInfoAction
from .activity_traverse_closure import ActivityTraverseClosure
from .ctor import Ctor
from .impl_base import ImplBase
from .activity_traverse_closure import ActivityTraverseClosure

class ActionImpl(ImplBase):
    
    # @staticmethod
    # def init(self, base, *args, **kwargs):
    #     ctor = vsc_impl.Ctor.inst()
    #     typeinfo = type(self)._typeinfo
        
    #     s = ctor.scope()
        
    #     if s is not None:
    #         if s.facade_obj is None:
    #             # The field-based caller has created a frame for us
    #             s.facade_obj = self
    #             if not ctor.is_type_mode():
    #                 s.lib_scope.setFieldData(self)
    #         elif s.facade_obj is self:
    #             s.inc_inh_depth()
    #         else:
    #             # Need to create a new scope
    #             if ctor.is_type_mode():
    #                 raise Exception("Should not hit in type mode")
    #             s = ctor.push_scope(
    #                 self,
    #                 ctor.ctxt().buildModelAction(
    #                     typeinfo.lib_obj,
    #                     type(self).__name__),
    #                 False)
    #             s.lib_scope.setFieldData(self)
    #     else:
    #         # Push a new scope, knowing that we're not in type mode
    #         if ctor.is_type_mode():
    #             raise Exception("Should not hit in type mode")
    #         s = ctor.push_scope(
    #             self,
    #             ctor.ctxt().buildModelAction(
    #                 typeinfo.lib_obj,
    #                 type(self).__name__),
    #             False)
    #         s.lib_scope.setFieldData(self)

        
    #     self._modelinfo = ModelInfo(self, "<>")
    #     self._modelinfo._lib_obj = s._lib_scope
        
    #     print("--> ActionImpl.__init__")
        
    #     # Add built-in 'comp' field
        
    #     # Populate the fields
    #     # Note: cannot ask for the object representation from DataClasses
    #     # before this step is performed
    #     for i,fc in enumerate(typeinfo._field_ctor_l):
    #         print("Action Field: %s" % fc[0])
    #         ctor.push_scope(None, s.lib_scope.getField(i))
    #         print("--> field.constructor", flush=True)
    #         field_facade = fc[1](fc[0])
    #         print("<-- field.constructor", flush=True)
    #         setattr(self, fc[0], field_facade)
    #         ctor.pop_scope()

    #     if not ctor.is_type_mode():            
    #         print("field_data: %s" % str(s.lib_scope.getFieldData()))
            

    #     # Invoke the user-visible constructor        
    #     print("--> ActionImpl.__init__.base", flush=True)
    #     base(self, *args, *kwargs)
    #     print("<-- ActionImpl.__init__.base", flush=True)
        
    #     print("<-- ActionImpl.__init__", flush=True)

    #     ctor.pop_scope()
    #     pass

    @staticmethod
    def __call__(self, *args, **kwargs):
        action_ti = TypeInfoAction.get(typeworks.TypeInfo.get(type(self)))
        ctor_a = Ctor.inst()
        print("ActionImpl.__call__")

        if len(args) > 0:
            raise Exception("Only kwargs can be passed to action traversal")

        if not ctor_a.activity_mode():
            raise Exception("Actions can only be called inside activities")

        # How do we determine where this field is instanced?
        target = ctor_a.ctxt().mkTypeExprFieldRef()
        target.addActiveScopeRef(-1)
        target.addIdxRef(self._modelinfo._lib_obj.getIndex())

        dt_traverse = ctor_a.ctxt().mkDataTypeActivityTraverse(
            target,
            None)
        ft_traverse = ctor_a.ctxt().mkTypeFieldActivity(
            "",
            dt_traverse,
            True)

        ctor_a.activity_scope().addActivity(ft_traverse)

        return ActivityTraverseClosure(dt_traverse)
    
    @staticmethod
    def getattribute(self, name):
        ctor = vsc_impl.Ctor.inst()
        ctor_a = Ctor.inst()
        ret = object.__getattribute__(self, name)

        # if ctor_a.activity_mode():
        #     # Need to get the path of the target field
        #     ctor_a.push_activity_mode(False)
        #     ctor.push_expr_mode(False)
        #     target = ctor_a.ctxt().mkTypeExprFieldRef()
        #     target.addRootRef()
        #     target.addIdxRef(ret._modelinfo._lib_obj.getIndex())
        #     print("Field: %d" % ret._modelinfo._lib_obj.getIndex())
        #     dt_traverse = ctor_a.ctxt().mkDataTypeActivityTraverse(
        #         target,
        #         None)

        #     ctor_a.activity_scope().addActivity(dt_traverse)
        #     ret = ActivityTraverseClosure(dt_traverse)
            
        #     print("TODO: Add an activity")
        #     ctor.pop_expr_mode()
        #     ctor_a.pop_activity_mode()
        if not ctor.expr_mode():
            # TODO: Check whether this is a 'special' field
            if hasattr(ret, "get_val"):
                ret = ret.get_val()
        
        return ret    
    
    @staticmethod
    def _createHook(cls, hndl):
        ctor = vsc_impl.Ctor.inst()

        s = ctor.scope()

        print("createHook: %s %s" % (str(hndl), str(s)))

        if s is None:
            # Push a scope with the backend object
            # on it. The class constructor will 
            # pop this scope on exit
            ctor.push_scope(None, hndl, False)
            inst = cls()
            print("createHook: id=%x" % id(inst), flush=True)
            hndl.setFieldData(inst)
        
    @staticmethod
    def _createInst(cls, name):
        ret = cls()
        return ret

    # @staticmethod
    # def createActionField(lib_field, name, idx, ti):
    #     ctor = vsc_impl.Ctor.inst()
    #     ctor_a = Ctor.inst()

    #     ctor.push_scope(None, lib_field, False)
        
    #     # Create the user facade for this field (lib_field) 
    #     inst = ti.info.Tp()

    #     if not ctor.is_type_mode():
    #         lib_field.setFieldData(inst)

    #     return inst

    @staticmethod
    def createCompField(lib_field, name, idx, ti : TypeInfoAction):
        ctor = vsc_impl.Ctor.inst()

        comp = None
        if ctor.is_type_mode():
            print("NOTE: createCompField in type mode")
            comp = ctor.scope(-2).facade_obj
            print("  scope_s: %d" % len(ctor._scope_s))
        else:
            print("NOTE: createCompField in non-type mode", flush=True)
            comp = vsc_impl.FieldRefImpl(name, idx)

        # We will need a full elaboration of the component,
        # since it may be needed to form constraints

        # lib_field is the containing context (the action)
#        ctor.push_scope(None, lib_field, ctor.is_type_mode())
#        comp = ti.component_ti.info.Tp()
#        print("comp: %s" % str(comp))

        return comp

#    @staticmethod
#    def get

    
    @classmethod
    def addMethods(cls, T):
        ImplBase.addMethods(T)
        T.__call__ = cls.__call__
#        base_init = T.__init__
#        setattr(T, "__super_init__", getattr(T, "__init__"))
#        setattr(T, "__init__", lambda self, *args, **kwargs: cls.init(
#            self, base_init, *args, **kwargs))
#        setattr(T, "_createInst", cls._createInst)
#        setattr(T, "__getattribute__", cls.getattribute)
