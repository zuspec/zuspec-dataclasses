
import vsc_dataclasses.impl as vsc_impl
import vsc_dataclasses.impl.context as vsc_ctxt

from .modelinfo_component import ModelInfoComponent

from .rt_ctxt import RtCtxt
from .ctor import Ctor
from .exec_group import ExecGroup
from .exec_kind_e import ExecKindE
from .type_info import TypeInfo

class TypeInfoComponent(TypeInfo):

    def __init__(self, info):
        super().__init__(info)
        self._action_t = []

    def init(self, 
        obj, 
        args, 
        kwargs, 
        modelinfo=None,
        ctxt_b=None):
        vsc_ctor = vsc_impl.Ctor.inst()
        print("== Component.init.entry %s %d" % (self.info.T.__name__, len(vsc_ctor._scope_s)))
        is_type_mode = vsc_ctor.is_type_mode()
        Ctor.inst().elab()

        print("==> Component.init %s %d" % (self.info.T.__name__, len(vsc_ctor._scope_s)))

        if modelinfo is None:
            modelinfo = ModelInfoComponent(obj, "<>", self)

        if ctxt_b is None:
            ctxt_b = vsc_ctor.ctxt().mkModelBuildContext(Ctor.inst().ctxt())

        obj.backend = None
        obj.isInit = False

        super().init(obj, args, kwargs, modelinfo, ctxt_b)

        s = vsc_ctor.scope()
        if s is None and not is_type_mode:
            print("TODO: call initialization sequence")
            self._runInitSeq(obj)
        print("<== Component.init %s %d" % (self.info.T.__name__, len(vsc_ctor._scope_s)))

    def createInst(
            self,
            modelinfo_p,
            name,
            idx):
        vsc_ctor = vsc_impl.Ctor.inst()

        # Note: createInst is only called when creating fields. This means that
        # we always need to provide a Field (ModelField/TypeField) as the 
        # parent. 

        print("createInst: pre-size: %d" % len(vsc_ctor._scope_s))
        vsc_ctor.push_scope(None, modelinfo_p.libobj.getField(idx), vsc_ctor.is_type_mode())
        field = self.info.Tp()
        print("createInst: post-size: %d" % len(vsc_ctor._scope_s))

        field._modelinfo.name = name
        field._modelinfo.idx = idx

        print("TODO: Add component-type field differently")
        modelinfo_p.addSubComponent(field._modelinfo)

        return field

    def _runInitSeq(self, obj):
        print("_runInitSeq")
        # TODO: invoke initialization methods
        obj._modelinfo.libobj.initCompTree()
        self._invokeInit(obj)

    def _invokeInit(self, obj):
        ctxt = RtCtxt.inst()

        typeinfo : TypeInfoComponent = obj._modelinfo._typeinfo

        if ExecKindE.InitDown in typeinfo._exec_m.keys():
            print("Component has InitDown")
            exec_g : ExecGroup = typeinfo._exec_m[ExecKindE.InitDown]

            ctxt.push_exec_group(exec_g)
            for e in exec_g.execs:
                e.func(obj)
            ctxt.pop_exec_group()

        for comp_mi in obj._modelinfo.component_fields:
            print("comp_mi: %s" % comp_mi.name)
            self._invokeInit(comp_mi.obj)

        # for fn in dir(obj):
        #     print("Component: fn=%s" % fn)
        #     if not fn.startswith("__"):
        #         fo = getattr(obj, fn)
        #         if hasattr(fo, "_modelinfo"):
        #             mi = fo._modelinfo
        #             if isinstance(mi._typeinfo, TypeInfoComponent):
        #                 print("Is a component")

        if ExecKindE.InitUp in typeinfo._exec_m.keys():
            print("Component has InitUp")
            exec_g : ExecGroup = typeinfo._exec_m[ExecKindE.InitUp]

            ctxt.push_exec_group(exec_g)
            for e in exec_g.execs:
                e.func(obj)
            ctxt.pop_exec_group()

    def elab(self, obj=None):
        vsc_ctor = vsc_impl.Ctor.inst()
        print("--> TypeInfoComponent.elab %s %d" % (self.info.T.__name__, len(vsc_ctor._scope_s)))
        if obj is None:
            print("Create object")
            # Push the data-type object for the component
            print("pre-create object %d" % len(vsc_ctor._scope_s))
            obj = self.createTypeInst()
#            vsc_ctor.push_scope(None, self.lib_typeobj, True)
#            obj = self.elab_obj_ctor()
#            vsc_ctor.pop_scope()
            print("post-create object %d" % len(vsc_ctor._scope_s))

        # Elab the component first
        super().elab(obj)

        # Since a lot of the 'fun' happens during elab, 
        # perhaps we should just have the component on a higher
        # scope?

        vsc_ctor.push_scope(obj, None, True) # We're definitely in type mode
        # Then, elab each of the actions
        for action_t in self._action_t:
            # The action must know the component type prior to
            # constructing the elaboration object
            action_t.component_ti = self

            print("--> Elab action %s %d" % (action_t.info.Tp.__name__, len(vsc_ctor._scope_s)))
#            obj_a = action_t.elab_obj_ctor()
            obj_a = action_t.createTypeInst()
            action_t.elab(obj_a)
            print("<-- Elab action %s %d" % (action_t.info.Tp.__name__, len(vsc_ctor._scope_s)))
        vsc_ctor.pop_scope()

        print("<-- TypeInfoComponent.elab %s %d" % (self.info.T.__name__, len(vsc_ctor._scope_s)))

    def addActionT(self, a):
        self._action_t.append(a)
        # Register with the backend component-type object
        self._lib_typeobj.addActionType(a._lib_typeobj)

    @staticmethod
    def get(info) -> 'TypeInfoComponent':
        if not hasattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME):
            setattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME, TypeInfoComponent(info))
        return getattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME)

    def createHook(self, obj):
        print("Note: skip Component createHook")
        pass
