
from typing import List
import zsp_dataclasses.impl.context as ctxt_api
import vsc_dataclasses.impl.context as vsc_ctxt
import vsc_dataclasses.impl.pyctxt as vsc_pyctxt
from .data_type_arl_struct import DataTypeArlStruct

class DataTypeAction(ctxt_api.DataTypeAction,DataTypeArlStruct):
    
    def __init__(self, ctxt: 'ctxt_api.Context', name):
        DataTypeArlStruct.__init__(self, name)
        super().__init__(name)
        self._comp_t = None
        self._activities = []
        self.addField(ctxt.mkTypeFieldRef(
            "comp", 
            None, 
            vsc_ctxt.TypeFieldAttr.NoAttr))
        print("Field: %s (%s)" % (self.getField(0).name(), type(self.getField(0)).__qualname__))

    def getComponentType(self) -> 'DataTypeComponent':
        return self._comp_t
    
    def setComponentType(self, t : 'DataTypeComponent'):
        print("setComponent")
        print("Field: %s (%s)" % (self.getField(0).name(), type(self.getField(0)).__qualname__))
        self.getField(0).setDataType(t)
        self._comp_t = t
        pass

    def getCompField(self) -> 'vsc_ctxt.TypeFieldRef':
        return self._fields[0]
    
    def addField(self, f: 'TypeField'):
        print("DataTypeAction.addField %s" % f.name())
        if f.name().endswith(".Entry"):
            raise Exception("Bad addition")
        return super().addField(f)

    def addActivity(self, activity : 'TypeFieldActivity'):
        self._activities.append(activity)

    def activities(self) -> List['TypeFieldActivity']:
        return self._activities
    
    def accept(self, v):
        v.visitDataTypeAction(self)
