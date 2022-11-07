
from typing import List
import arl_dataclasses.impl.context as ctxt_api
import vsc_dataclasses.impl.context as vsc_ctxt
import vsc_dataclasses.impl.pyctxt as vsc_pyctxt

class DataTypeAction(ctxt_api.DataTypeAction,vsc_pyctxt.DataTypeStruct):
    
    def __init__(self, ctxt: 'ctxt_api.Context', name):
        super().__init__(name)
        self._comp_t = None
        self._activities = []
        self.addField(ctxt.mkTypeFieldRef(
            "comp", 
            None, 
            vsc_ctxt.TypeFieldAttr.NoAttr))

    def getComponentType(self) -> 'DataTypeComponent':
        return self._comp_t
    
    def setComponentType(self, t : 'DataTypeComponent'):
        self.getField(0).setDataType(t)
        self._comp_t = t

    def getCompField(self) -> 'vsc_ctxt.TypeFieldRef':
        return self._fields[0]

    def addActivity(self, activity : 'TypeFieldActivity'):
        self._activities.append(activity)

    def activities(self) -> List['TypeFieldActivity']:
        return self._activities
