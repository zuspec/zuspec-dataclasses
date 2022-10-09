
import arl_dataclasses.impl.context as ctxt_api
import vsc_dataclasses.impl.pyctxt as vsc_pyctxt
from .data_type_action import DataTypeAction
from .data_type_component import DataTypeComponent

class Context(vsc_pyctxt.Context,ctxt_api.Context):

    def __init__(self):
        super().__init__()
        self._action_t_m = {}
        self._comp_t_m = {}

    def findDataTypeAction(self, name) -> 'DataTypeAction':
        if name in self._action_t_m.keys():
            return self._action_t_m[name]
        else:
            return None
    
    def mkDataTypeAction(self, name) -> DataTypeAction:
        return DataTypeAction(name)

    def addDataTypeAction(self, t : DataTypeAction) -> bool:
        if t._name not in self._action_t_m.keys():
            self._action_t_m[t._name] = t
            return True
        else:
            return False

    def findDataTypeComponent(self, name) -> 'DataTypeComponent':
        if name in self._comp_t_m.keys():
            return self._comp_t_m[name]
        else:
            return None

    def mkDataTypeComponent(self, name) -> 'DataTypeComponent':
        return DataTypeComponent(name)

    def addDataTypeComponent(self, t : 'DataTypeComponent') -> bool:
        if t._name not in self._comp_t_m.keys():
            self._comp_t_m[t._name] = t
            return True
        else:
            return False
