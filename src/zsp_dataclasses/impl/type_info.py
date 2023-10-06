'''
Created on Apr 4, 2022

@author: mballance
'''
import dataclasses
import vsc_dataclasses.impl as vsc_impl
import zsp_dataclasses.impl.context as ctxt_api
from typing import Dict, List, Tuple
from .exec_kind_e import ExecKindE
from .exec_group import ExecGroup
from .constraint_impl import ConstraintImpl
from .exec_type import ExecType
from .method_proxy_fn import MethodProxyFn

class TypeInfo(vsc_impl.TypeInfoRandClass):
    
    def __init__(self, info):
        super().__init__(info)
        
        self._is_elab = False
        
        # Only meaningful for actions
        self._ctxt_t = None

        # Dict of exec kind to list of exec blocks
        self._exec_m : Dict[ExecKindE,ExecGroup] = {}
        
        # List of constraints
        self._constraint_l : List[ConstraintImpl] = []
        
        # List of field-name, field-constructor
        self._field_ctor_l : Tuple[str,object] = []

        # List of type extensions
        self._extension_l = []

        self._function_l : List[MethodProxyFn] = []

    def addExec(self, exec_t : ExecType):
        print("TypeInfo.addExec")
        if exec_t.kind not in self._exec_m.keys():
            self._exec_m[exec_t.kind] = ExecGroup(exec_t.kind)
        self._exec_m[exec_t.kind].add_exec(exec_t)

    def setExecSuper(self, super_ti : 'TypeInfo'):
        for kind in self._exec_m.keys():
            if kind in super_ti._exec_m.keys():
                self._exec_m[kind].super = super_ti._exec_m[kind]
        for kind in super_ti._exec_m.keys():
            if kind in self._exec_m.keys():
                self._exec_m[kind].super = super_ti._exec_m[kind]
            else:
                self._exec_m[kind] = super_ti._exec_m[kind]

    def addExtension(self, ext):
        self._extension_l.append(ext)

    @property
    def kind(self):
        return self._kind
    
    @kind.setter
    def kind(self, _kind):
        self._kind = _kind
        
    @property
    def ctxt_t(self):
        return self._ctxt_t
    
    @ctxt_t.setter
    def ctxt_t(self, _ctxt_t):
        self._ctxt_t = _ctxt_t
        
    @property
    def is_elab(self):
        return self._is_elab

    def elab(self, obj):
        super().elab(obj)
        self._elabExecs(obj)
        self._is_elab = True

    def _elabExecs(self, obj):
        from .ctor import Ctor, CtxtE
        exec_kind_m = {
            ExecKindE.Body : ctxt_api.ExecKindT.Body,
            ExecKindE.InitDown : ctxt_api.ExecKindT.InitDown,
            ExecKindE.InitUp : ctxt_api.ExecKindT.InitUp,
            ExecKindE.PreSolve : ctxt_api.ExecKindT.PreSolve,
            ExecKindE.PostSolve : ctxt_api.ExecKindT.PostSolve
        }

        ctxt = Ctor.inst().ctxt()
        for kind in self._exec_m.keys():
            print("Elaborating exec-kind %s" % str(kind))
            root_scope = None
            scope = None
            for e in self._exec_m[kind].execs:
                print("  Exec %s" % str(e))
                if scope is not None:
                    if root_scope is None:
                        root_scope = ctxt.mkTypeProcStmtScope()
                    root_scope.addStatement(scope)
                scope = ctxt.mkTypeProcStmtScope()
                Ctor.inst().push_ctxt_type(CtxtE.Exec)
                Ctor.inst().push_proc_scope(scope)
                e.func(obj)
                Ctor.inst().pop_proc_scope()
                Ctor.inst().pop_ctxt_type()

                if root_scope is not None:
                    root_scope.addStatement(scope)
            if root_scope is not None:
                self._lib_typeobj.addExec(
                    ctxt.mkTypeExec(exec_kind_m[kind], root_scope))
            else:
                self._lib_typeobj.addExec(
                    ctxt.mkTypeExec(exec_kind_m[kind], scope))

    def _elabFields(self):
        from .rand_t import RandT
        from .scalar_t import ScalarT
        from .pool_t import PoolT
        from .lock_share_t import LockShareT

        for f in dataclasses.fields(self._Tp):

            attr = vsc.ModelFieldFlag.NoFlags
            is_rand = False
            iv=0

            if type(f.type) == str:
#                raise Exception("Type %s is forward declared" % t)
                raise Exception("Field %s has an unresolved type %s" % (f.name, f.type))
            
            t = f.type

            if issubclass(t, RandT):
                t = t.T
                attr |= vsc.ModelFieldFlag.DeclRand
                is_rand = True

            ctor = vsc_impl.Ctor.inst()

            print("f: %s" % str(f))
            
            # The signature of a creation function is:
            # - name
            # - is_rand
            # - idx
            if issubclass(t, ScalarT):
                self._elabFieldScalar(f, attr, t)
            elif issubclass(t, PoolT):
                self._elabFieldPool(f, attr, t)
            elif issubclass(t, LockShareT):
                print("LockShare!")
                self._elabFieldLockShare(f, attr, t)
            elif hasattr(t, "_typeinfo") and isinstance(t._typeinfo, TypeInfo):
                # This is a field of user-defined type
                print("Has TypeInfo")
                field_t = ctor.ctxt().mkTypeFieldPhy(
                    f.name, 
                    t._typeinfo.lib_obj,
                    False,
                    attr,
                    None)
                self.lib_obj.addField(field_t)
                self._field_ctor_l.append((f.name, lambda name, t=t: t._createInst(t, name)))
                
            print("Field: %s" % str(f))
            
    def _elabFieldLockShare(self, f, attr, t):
        ctor = vsc_impl.Ctor.inst()
        
        if hasattr(t.T, "_typeinfo"):
            print("Kind: %s" % str(t.T._typeinfo._kind))
            claim_t = t.T._typeinfo.lib_obj
        else:
            raise Exception("Type %s is not a PyRctGen type" % t.T.__qualname__)
        
        if f.default is not dataclasses.MISSING:
            print("default: %s" % str(f.default))
            raise Exception("Lock/Share fields cannot be assigned a value")
        
        field_t = ctor.ctxt().mkTypeFieldClaim(
            f.name,
            claim_t,
            t.IsLock)

        self.lib_obj.addField(field_t)
        self._field_ctor_l.append((f.name, t.createField))        

    def _processFieldPool(self, ti, f, attr, t):
        ctor = vsc_impl.Ctor.inst()
        decl_size = -1
        
        pool_t = None
        
        if hasattr(t.T, "_typeinfo"):
            print("Kind: %s" % str(t.T._typeinfo._kind))
            pool_t = t.T._typeinfo.lib_obj
        else:
            raise Exception("Type %s is not a PyRctGen type" % t.T.__qualname__)
        
        if f.default is not dataclasses.MISSING:
            if t.T._typeinfo._kind != StructKindE.Resource:
                raise Exception("Only resource pools may be given a size. Pool %s is of kind %s" % (
                    f.name, t.T._typeinfo._kind))
            decl_size = int(f.default)
        
        field_t = ctor.ctxt().mkTypeFieldPool(
            f.name,
            pool_t,
            attr,
            decl_size)

        ti.lib_obj.addField(field_t)
        ti._field_ctor_l.append((f.name, t.createField))
        
    def _elabFieldScalar(self, f, attr, t):
        ctor = vsc_impl.Ctor.inst()
        lt = ctor.ctxt().findDataTypeInt(t.S, t.W)
        if lt is None:
            lt = ctor.ctxt().mkDataTypeInt(t.S, t.W)
            ctor.ctxt().addDataTypeInt(lt)

        iv_m = None
        
        if f.default is not dataclasses.MISSING:
            iv_m = ctor.ctxt().mkModelVal()
            iv_m.setBits(t.W)
            if t.S:
                iv_m.set_val_i(int(f.default))
            else:
                iv_m.set_val_u(int(f.default))
            
        field_t = ctor.ctxt().mkTypeFieldPhy(
            f.name, 
            lt, 
            False,
            attr,
            iv_m)
        self.lib_obj.addField(field_t)
        self._field_ctor_l.append((f.name, t.createField))        

    @staticmethod
    def get(info, check=False):
        if not hasattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME):
            if not check:
                raise Exception("TypeInfo is an abstract class")
            else:
                return None
        return getattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME)

    def createHook(self, obj):
        print("TypeInfo: createHook")
        ctor = vsc_impl.Ctor.inst()

        s = ctor.scope()

        print("createHook: %s %s" % (str(obj), str(s)))

        if s is None:
            # Push a scope with the backend object
            # on it. The class constructor will 
            # pop this scope on exit
            ctor.push_scope(None, obj, False)
            inst = self.info.Tp()
            print("createHook: id=%x" % id(inst), flush=True)
            obj.setFieldData(inst)
