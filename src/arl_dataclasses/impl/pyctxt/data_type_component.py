
import arl_dataclasses.impl.context as ctxt_api
import vsc_dataclasses.impl.context as vsc_ctxt
import vsc_dataclasses.impl.pyctxt as vsc_pyctxt
from typing import List
from .model_field_component import ModelFieldComponent

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

    def mkRootField(self,
        ctxt : 'ModelBuildContext',
        name : str,
        is_ref : bool) -> 'ModelFieldComponent':
        ret = ModelFieldComponent(name, self)

        # Build out fields
        for tf in self._fields:
            ret.addField(tf.mkModelField(ctxt))

        # TODO: build out constraints
        return ret

