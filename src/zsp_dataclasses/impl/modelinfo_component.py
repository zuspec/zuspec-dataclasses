
import vsc_dataclasses.impl as vsc_impl

class ModelInfoComponent(vsc_impl.ModelInfo):
    
    def __init__(self, obj, name, typeinfo):
        super().__init__(obj, name, typeinfo)
        self.component_fields = []
        pass

    def addSubComponent(self, comp_mi):
        self.addSubfield(comp_mi)
        self.component_fields.append(comp_mi)
