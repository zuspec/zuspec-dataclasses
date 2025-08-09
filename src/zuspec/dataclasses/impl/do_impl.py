
import typeworks
import vsc_dataclasses.impl.context as vsc_ctxt
from .activity_traverse_closure import ActivityTraverseClosure
from .ctor import Ctor
from .typeinfo_action import TypeInfoAction

class DoImpl(object):

    def __init__(self, *args, **kwargs):
        print("DoImpl: %s" % str(kwargs))
        pass

    def __getitem__(self, T):
        ctor_a = Ctor.inst()

        ti = typeworks.TypeInfo.get(T, False)
        if ti is None:
            raise Exception("Type %s is not an action" % str(T))
        action_ti = TypeInfoAction.get(ti)

        print("DoImplMeta: %s" % str(action_ti.lib_typeobj), flush=True)
        
        # Add a field declaration to the activity scope
        field_t = ctor_a.ctxt().mkTypeFieldPhy(
            "__tmp__",
            action_ti.lib_typeobj,
            False,
            vsc_ctxt.TypeFieldAttr.NoAttr,
            None)
        inst = action_ti.createTypeInst()
        
        ctor_a.activity_scope().addField(field_t)

        target = ctor_a.ctxt().mkTypeExprFieldRef()
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
        
        ctor_a.activity_scope().addActivity(ft_traverse)
        
        # Add a traversal statement to the current activity scope
        return ActivityTraverseClosure(dt_traverse, inst)
