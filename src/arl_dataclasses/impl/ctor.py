'''
Created on Mar 19, 2022

@author: mballance
'''

import typeworks

from .type_info import TypeInfo
from .type_kind_e import TypeKindE
from .ctor_scope import CtorScope
from .pyctxt.context import Context

class Ctor(object):
    _inst = None
    
    def __init__(self):
        self._is_elab = False
        self._component_type_m = {}
        self._exec_type_l = []
        self._ctxt = None
        self._scope_s = []
        self._action_decl_l = []
        self._activity_l = []
        self._activity_scope_s = []
        self._constraint_l = []
        self._constraint_s = []
        self._expr_s = []
        self._expr_mode_s = []
        self._activity_mode_s = []
 
        self._component_l = []
        self._action_typeinfo_m = {}       
        self._activity_s = []

        pass
    
    def ctxt(self):
        if self._ctxt is None:
            raise Exception("No backend provided for arl_dataclasses")
        return self._ctxt
    
    def elab(self):
        if self._is_elab:
            print("Skip elab")
            return
        self._is_elab = True

        components = typeworks.TypeRgy.get_types(TypeKindE.Component)
        print("Elab with %d components" % len(components))
        
        for c in components:
            c_ti = TypeInfo.get(c)
            c_ti.elab()
        
    
    def scope(self):
        if len(self._scope_s) > 0:
            return self._scope_s[-1]
        else:
            return None
        
    def push_scope(self, facade_obj, lib_scope, type_mode=None):
        if type_mode is None:
            if len(self._scope_s) == 0:
                raise Exception("Cannot pass type_mode=None without a scope entry")
            type_mode = self._scope_s[-1]._type_mode
        s = CtorScope(facade_obj, lib_scope, type_mode)
        self._scope_s.append(s)
        self.push_bo
        return s
        
    def pop_scope(self):
        self._scope_s.pop()
        
    def is_type_mode(self):
        return len(self._scope_s) > 0 and self._scope_s[-1]._type_mode
        
    def push_expr(self, e):
        self._expr_s.append(e)
        
    def pop_expr(self):
        self._expr_s.pop()
        
    def expr(self):
        if len(self._expr_s) > 0:
            return self._expr_s[-1]
        else:
            return None
        
    def activity_mode(self):
        return len(self._activity_mode_s) > 0 and self._activity_mode_s[-1]
    
    def push_activity_mode(self, m=True):
        self._activity_mode_s.append(m)
        
    def pop_activity_mode(self):
        return self._activity_mode_s.pop()
        
    def push_expr_mode(self, m=True):
        self._expr_mode_s.append(m)
        
    def expr_mode(self):
        return len(self._expr_mode_s) > 0 and self._expr_mode_s[-1]
        
    def pop_expr_mode(self):
        return self._expr_mode_s.pop()
    
    def push_action_decl(self, Ta):
        self._action_decl_l.append(Ta)
        
    def pop_action_decl(self):
        ret = self._action_decl_l.copy()
        self._action_decl_l.clear()
        return ret
    
    def push_activity_decl(self, a):
        self._activity_l.append(a)
    
    def pop_activity_decl(self):
        ret = self._activity_l.copy()
        self._activity_l.clear()
        return ret
    
    def push_activity_scope_mi(self, s_mi):
        from vsc_dataclasses.impl import Ctor as VscCtor
        VscCtor.inst().push_bottom_up_mi(s_mi)
#        self._activity_s.append(s)
    
    def pop_activity_scope_mi(self):
        from vsc_dataclasses.impl import Ctor as VscCtor
        VscCtor.inst().pop_bottom_up_mi()
#        self._activity_s.pop()

    def add_activity(self, activity_ft):
        """Adds an activity field type to the containing activity data-type scope"""
        from vsc_dataclasses.impl import Ctor as VscCtor
        VscCtor.inst().bottom_up_mi().libobj.addActivity(activity_ft)

    def add_anonymous_traversal(self, action_ti):
        from vsc_dataclasses.impl import Ctor as VscCtor
        import vsc_dataclasses.impl.context as vsc_ctxt
        ctor = VscCtor.inst()

        # Add a field declaration to the activity scope
        field_t = ctor.ctxt().mkTypeFieldPhy(
            action_ti.info.T.__qualname__,
            action_ti.lib_typeobj,
            False,
            vsc_ctxt.TypeFieldAttr.NoAttr,
            None)
        
        ctor.bottom_up_mi().libobj.addField(field_t)
        ctor.push_scope(None, field_t, True)
        field = action_ti.createTypeInst()
        ctor.pop_scope()

        print("Scope for tempvar is: %s" % str(ctor.bottom_up_mi()))
        field._modelinfo.idx = len(ctor.bottom_up_mi()._subfield_modelinfo)
        ctor.bottom_up_mi().addSubfield(field._modelinfo)
        print("field._modelinfo.parent=%s" % str(field._modelinfo._parent))

        return (field_t, field)
        
    def push_constraint_decl(self, c):
        self._constraint_l.append(c)
        
    def pop_constraint_decl(self):
        ret = self._constraint_l.copy()
        self._constraint_l.clear()
        return ret
    
    def push_constraint_scope(self, c):
        self._constraint_s.append(c)
        
    def constraint_scope(self):
        return self._constraint_s[-1]
    
    def pop_constraint_scope(self):
        # Collect remaining expressions and convert to expr_statements
        cb = self._constraint_s.pop()
        
        for e in self._expr_s:
            if self.is_type_mode():
                c = self.ctxt().mkTypeConstraintExpr(e._model)
            else:
                c = self.ctxt().mkModelConstraintExpr(e._model)
            cb.addConstraint(c)
        self._expr_s.clear()
            
        return cb    
    
    def push_exec_type(self, e):
        self._exec_type_l.append(e)
        
    def pop_exec_types(self):
        ret = self._exec_type_l.copy()
        self._exec_type_l.clear()
        return ret
    
    def add_component(self, T):
        self._component_l.append(T)
        
    def components(self):
        return self._component_l
        
    def add_action_typeinfo(self, T, typeinfo):
        self._action_typeinfo_m[T] = typeinfo
        
    def finalize(self):
        """Perform final setup setps"""
        pass
    
    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = Ctor()
        return cls._inst

    @classmethod
    def init(cls, ctxt):
        cls._inst = Ctor()
        cls._inst._ctxt = ctxt

    