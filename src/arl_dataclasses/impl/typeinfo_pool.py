
import vsc_dataclasses.impl as vsc_impl

from .field_pool_impl import FieldPoolImpl

class TypeInfoPool(vsc_impl.TypeInfoField):

    def createInst(
        self, 
        modelinfo_p, 
        name, 
        idx):
        ctor = vsc_impl.Ctor.inst()

        ret = FieldPoolImpl(name, self.typeinfo, idx)
        ret._modelinfo.libobj = modelinfo_p.libobj.getField(idx)
        modelinfo_p.addSubfield(ret._modelinfo)

        return ret


