
import vsc_dataclasses.impl as vsc_impl

class TypeInfoCompRef(vsc_impl.TypeInfoRef):

    def __init__(self):
        super().__init__(None)
        self.component_ti = None

    def setComponentTi(self, component_ti):
        self.component_ti = component_ti
        self.target_ti = component_ti
        self.ti = component_ti

    def createInst(
            self, 
            modelinfo_p, 
            name, 
            idx):
        print("==> TypeInfoCompRef.createInst")
        ctor = vsc_impl.Ctor.inst()

        if ctor.is_type_mode():
            # Create an actual component field
            field = self.component_ti.createTypeInst()
            field._modelinfo.name = name
            field._modelinfo.idx = idx
            modelinfo_p.addSubfield(field._modelinfo)
            ret = field
        else:
            ret = super().createInst(modelinfo_p, name, idx)
        print("<== TypeInfoCompRef.createInst")
        return ret