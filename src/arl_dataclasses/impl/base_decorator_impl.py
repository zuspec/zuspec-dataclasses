

import typeworks
import vsc_dataclasses.impl as vsc_impl
from .activity_decl import ActivityDecl

from .exec_type import ExecType
from .type_info import TypeInfo

class BaseDecoratorImpl(vsc_impl.RandClassDecoratorImpl):

    def pre_decorate(self, T):
        base_ti : TypeInfo = TypeInfo.get(self.get_typeinfo())

        # collect exec blocks registers in this scope
        for exec_ti in typeworks.DeclRgy.pop_decl(ExecType, typeworks.scopename(T)):
            print("Add exec block %s %s" % (str(exec_ti), str(T)))
            print("  annotations: %s" % str(exec_ti.func.__annotations__))
            base_ti.addExec(exec_ti)
        
        # Now, link up the 'super' relationships
        super_ti = self._get_super_ti(T)
        if super_ti is not None:
            base_ti.setExecSuper(super_ti)

        # pre-decorate will create the native type object
        super().pre_decorate(T)

        # Now, register an object-creation hook
        base_ti.lib_typeobj.setCreateHook(lambda obj: base_ti.createHook(obj))

    def _get_super_ti(self, T):
        if len(T.__bases__) > 0:
            ti = typeworks.TypeInfo.get(T.__bases__[0], False)
            if ti is not None:
                super_ti = TypeInfo.get(ti, True)
                if super_ti is not None:
                    # Have an actual base here
                    return super_ti
        return None



