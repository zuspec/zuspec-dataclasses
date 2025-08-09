
import vsc_dataclasses.impl as vsc_impl

from .ctor import Ctor, CtxtE
from .modelinfo_activity import ModelinfoActivity
from .type_info import TypeInfo

class TypeInfoAction(TypeInfo):

    def __init__(self, info):
        super().__init__(info)
        self.activities = []
        self.activity_super = None
        self._component_ti = None

    def init(self, obj, args, kwargs, modelinfo=None, ctxt_b=None):
        ctor_a = Ctor.inst()
        ctor_vsc = vsc_impl.Ctor.inst()
        print("==> Action.init %s %d" % (self.info.T.__name__, len(ctor_vsc._scope_s)))

        if ctxt_b is None:
            ctxt_b = ctor_vsc.ctxt().mkModelBuildContext(Ctor.inst().ctxt())

        super().init(obj, args, kwargs, modelinfo, ctxt_b)

        print("<== Action.init %s %d" % (self.info.T.__name__, len(ctor_vsc._scope_s)))

    @property
    def component_ti(self):
        return self._component_ti

    @component_ti.setter
    def component_ti(self, v):
        self._component_ti = v

        # Ensure the 'comp' handle knows
        self._field_typeinfo[0].typeinfo.setComponentTi(v)

    def elab(self, obj):
        print("TypeInfoAction.elab")
        print("Field[0]=%s" % self.lib_typeobj.getField(0).name())
        self.lib_typeobj.setComponentType(self.component_ti.lib_typeobj)
        print("Field[0]=%s" % self.lib_typeobj.getField(0).name())
        super().elab(obj)
        print("Field[0]=%s" % self.lib_typeobj.getField(0).name())

        self.elabActivities(obj)
        print("Field[0]=%s" % self.lib_typeobj.getField(0).name())
        pass

    def addActivity(self, activity_t):
        self.activities.append(activity_t)

    def createInst(
        self,
        modelinfo_p,
        name,
        idx):
        print("TypeInfoAction::createInst")
        ctor = vsc_impl.Ctor.inst()
        ctor.push_scope(
            None, 
            modelinfo_p.libobj.getField(idx),
            ctor.is_type_mode())
        field = self.info.Tp()
        field._modelinfo.name = name
        field._modelinfo.idx = idx
        modelinfo_p.addSubfield(field._modelinfo)

        return field
    
    # def createTypeInst(self):
    #     obj = super().createTypeInst()
    #     print("LibObj: %s" % str(obj._modelinfo.libobj))

    def elabActivities(self, obj):
        ctor_a = Ctor.inst()
        ctor = vsc_impl.Ctor.inst()
        # Save the current scope stack and clear it. This allows us to
        # treat the activity scope as a distinct scope
        scopes = ctor.save_scopes()
        ctor.push_type_mode()
        ctor_a.push_ctxt_type(CtxtE.Activity)
        for a in self.activities:
            activity_s = ctor_a.ctxt().mkDataTypeActivitySequence()
            activity_mi = ModelinfoActivity(activity_s)
            print("activity_s: %s" % str(activity_s))
            activity_f = ctor_a.ctxt().mkTypeFieldActivity(
                    "activity",
                    activity_s,
                    True)

            # Add the activity to the action's type object
            self.lib_typeobj.addActivity(activity_f)
            print("activity index=%d" % activity_f.getIndex())
            
            ctor_a.push_activity_scope_mi(activity_mi)
            print("--> activity")
            a.func(obj)
            print("<-- activity %d", len(activity_s.getActivities()))
            ctor_a.pop_activity_scope_mi()

        ctor.pop_type_mode()
        ctor_a.pop_ctxt_type()
        ctor.restore_scopes(scopes)
        pass

    @staticmethod
    def get(info) -> 'TypeInfoAction':
        if not hasattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME):
            setattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME, TypeInfoAction(info))
        return getattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME)

    # def createHook(self, obj):
    #     print("TypeInfoAction: createHook")
    #     ctor = vsc_impl.Ctor.inst()

    #     s = ctor.scope()

    #     print("createHook: %s %s" % (str(obj), str(s)))

    #     if s is None:
    #         # Push a scope with the backend object
    #         # on it. The class constructor will 
    #         # pop this scope on exit
    #         ctor.push_scope(None, obj, False)
    #         inst = self.info.Tp()
    #         print("createHook: id=%x" % id(inst), flush=True)
    #         obj.setFieldData(inst)
