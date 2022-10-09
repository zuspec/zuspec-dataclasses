
from typing import List
import arl_dataclasses.impl.context as ctxt_api
import vsc_dataclasses.impl.context as vsc_ctxt
import vsc_dataclasses.impl.pyctxt as vsc_pyctxt

class DataTypeComponent(vsc_pyctxt.DataTypeStruct, ctxt_api.DataTypeComponent):
    def __init__(self, name):
        super().__init__(name)
        self._action_types = []
        self._pool_binds = []

    def getActionTypes(self) -> List['DataTypeAction']:
        return self._action_types

    def addActionType(self, t : 'DataTypeAction'):
        self._action_types.append(t)

    def addPoolBindDirective(self, bind : 'PoolBindDirective'):
        self._pool_binds.append(bind)
