'''
Created on Apr 30, 2022

@author: mballance
'''

import typeworks
from .ctor import Ctor
import vsc_dataclasses.impl as vsc_impl
import vsc_dataclasses.impl.context as vsc_ctxt
from .activity_traverse_closure import ActivityTraverseClosure
from .type_info import TypeInfo
from .typeinfo_action import TypeInfoAction

class DoImplMeta(type):

    def __init__(self, name, bases, dct):
        pass
        
    def __getitem__(self, item):
        ctor_a = Ctor.inst()
        ctor = vsc_impl.Ctor.inst()

        ti = typeworks.TypeInfo.get(item, False)
        if ti is None:
            raise Exception("Type %s is not an action" % str(item))
        action_ti = TypeInfoAction.get(ti)

        print("DoImplMeta: %s" % str(action_ti.lib_typeobj), flush=True)
        
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

        # Link the field into the containing scope

        # Get a reference to this field
#        target = field_t.mkFieldRefExpr()

        target = ctor.ctxt().mkTypeExprFieldRef()
        target.addIdxRef(field_t.getIndex())
        target.addActiveScopeRef(-1)

        dt_traverse = ctor_a.ctxt().mkDataTypeActivityTraverse(
            target,
            None)
        print("dt_traverse: %s" % str(dt_traverse), flush=True)
        ft_traverse = ctor_a.ctxt().mkTypeFieldActivity(
            "",
            dt_traverse,
            True)
        
        ctor.bottom_up_mi().libobj.addActivity(ft_traverse)

        
        # Add a traversal statement to the current activity scope
        return ActivityTraverseClosure(dt_traverse, field)
    
