'''
Created on Apr 4, 2022

@author: mballance
'''

import vsc_dataclasses.impl as vsc_impl

from .backend_asyncio import BackendAsyncio
from .context import ModelEvalNodeT
from .typeinfo_component import TypeInfoComponent
from .typeinfo_action import TypeInfoAction
from .ctor import Ctor
from .type_info import TypeInfo
from .exec_kind_e import ExecKindE
from .exec_group import ExecGroup
from .rt_ctxt import RtCtxt
from .impl_base import ImplBase

class ComponentImpl(ImplBase):
    """Methods added to Component-decorated classes"""

    @staticmethod
    def setBackend(self, backend):
        self.backend = backend

    @staticmethod
    def getBackend(self):
        if self.backend is None:
            self.backend = BackendAsyncio()
            pass

        return self.backend

    # @staticmethod
    # def createCompField(
    #     modelinfo, 
    #     name, 
    #     idx, 
    #     ti : TypeInfoComponent):
    #     ctor = vsc_impl.Ctor.inst()

    #     s = ctor.scope()
    #     lib_field = s.lib_scope.getField(idx)

    #     print("createCompField: lib_field %s" % str(lib_field))
    #     ctor.push_scope(None, lib_field, ctor.is_type_mode())
    #     field = ti.info.Tp()

    #     modelinfo.component_fields.append(field)

    #     return field
    
    @staticmethod
    async def eval(self, action_t):
        randstate = vsc_impl.RandState.mk()

        ctor_v = vsc_impl.Ctor.inst()
        print("ComponentImpl.eval %d" % len(ctor_v._scope_s))
        ctor = Ctor.inst()
        ev = ctor.ctxt().mkModelEvaluator()
        action_ti = TypeInfoAction.get(action_t._typeinfo)
        it = ev.eval(
            randstate._model,
            self._modelinfo.libobj,
            action_ti._lib_typeobj)

        print("Iterating...")        
        await self._evalThread(it, 0)

    @staticmethod
    async def _evalThread(self, it, depth):
        backend = self.getBackend()

        valid = it.next()
        print("Initial: valid=%s" % valid)
        while valid:

            print("Next: %s depth=%d" % (it.type(), depth), flush=True)
            if it.type() == ModelEvalNodeT.Action:
                action_field = it.action()
                print("action_field: %s" % str(action_field))
                print("--> invoke getFieldData", flush=True)
                action = action_field.getFieldData()

                comp_ref_f = action_field.getField(0) # Get Component field
                comp = comp_ref_f.getRef()

                if comp is None:
                    raise Exception("Internal error: comp handle is null")

#                action.comp = comp.getFieldData()
                print("<-- invoke getFieldData", flush=True)
                print("--> invoke evalExecTarget", flush=True)
                await action._evalExecTarget(ExecKindE.Body)
                print("<-- invoke evalExecTarget", flush=True)
            
                print("Action: %s" % str(action))

                # Advance the iterator
                valid = it.next()
            elif it.type() == ModelEvalNodeT.Parallel:
                branch_it = it.iterator()

                # Advance the iterator off the parallel
                valid = it.next()

                task_l = []
                # Wait for coroutines to complete
                print("TODO: evaluate parallel")
                # Create a coroutine for each branch
                branch_it_v = branch_it.next()
                while branch_it_v:

                    branch = branch_it.iterator()
                    branch_it_v = branch_it.next()
                    print("Task:", flush=True)
                    # TODO: create a new co-routine task (pass thread iterator)
                    task_l.append(backend.fork(self._evalThread(branch, depth+1)))

                print("TODO: join")
                for t in task_l:
                    await backend.join(t)
                # TODO: join on all branches
                    pass
            elif it.type() == ModelEvalNodeT.Sequence:
                # Iterate through each item and dispatch
                print("TODO: evaluate sequence")
                pass
            else:
                raise Exception("Unknown iteration type %s" % it.type())
        
    @staticmethod
    def _createInst(cls, name):
        ret = cls()
        return ret
    
    @classmethod
    def addMethods(cls, T):
        ImplBase.addMethods(T)
#        base_init = T.__init__
#        setattr(T, "__init__", lambda self, *args, **kwargs: cls.init(
#            self, base_init, *args, **kwargs))
        setattr(T, "setBackend", cls.setBackend)
        setattr(T, "getBackend", cls.getBackend)
        setattr(T, "eval", cls.eval)
        setattr(T, "_evalThread", cls._evalThread)
        