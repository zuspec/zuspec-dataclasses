
from enum import IntEnum
from tokenize import Intnumber
from typing import List
import vsc_dataclasses as vsc

import vsc_dataclasses.impl.context as vsc_ctxt

class DataTypeAction(vsc_ctxt.DataTypeStruct):

    def getComponentType(self) -> 'DataTypeComponent':
        raise NotImplementedError("getComponentType")
    
    def setComponentType(self, t : 'DataTypeComponent'):
        raise NotImplementedError("setComponentType")

    def getCompField(self) -> 'vsc_ctxt.TypeFieldRef':
        raise NotImplementedError("getCompField")

    def addActivity(self, activity : 'TypeFieldActivity'):
        raise NotImplementedError("addActivity")

    def activities(self) -> List['TypeFieldActivity']:
        raise NotImplementedError('activities')

class DataTypeComponent(vsc_ctxt.DataTypeStruct):

    def getActionTypes(self) -> List[DataTypeAction]:
        raise NotImplementedError("getActionTypes")

    def addActionType(self, t : DataTypeAction):
        raise NotImplementedError("addActionType")

    def addPoolBindDirective(self, bind : 'PoolBindDirective'):
        raise NotImplementedError("addPoolBindDirective")

class FlowObjKindE(IntEnum):
    Buffer   = 0
    Resource = 1
    State    = 2
    Stream   = 3

class ModelEvalNodeT(IntEnum):
    Action = 0

class PoolBindKind(IntEnum):
    All = 0

class Context(vsc.impl.Context):

    def findDataTypeAction(self, name) -> 'DataTypeAction':
        raise NotImplementedError("findDataTypeAction")
    
    def mkDataTypeAction(self, name) -> DataTypeAction:
        raise NotImplementedError("mkDataTypeAction")

    def addDataTypeAction(self, t : DataTypeAction) -> bool:
        raise NotImplementedError("addDataTypeAction")

    def mkDataTypeActivityParallel(self) -> 'DataTypeActivityParallel':
        raise NotImplementedError("mkDataTypeActivityParallel")

    def mkDataTypeActivitySchedule(self) -> 'DataTypeActivitySchedule':
        raise NotImplementedError("mkDataTypeActivitySchedule")

    def mkDataTypeActivitySequence(self) -> 'DataTypeActivitySequence':
        raise NotImplementedError("mkDataTypeActivitySequence")

    def mkDataTypeActivityTraverse(self, target : 'vsc_ctxt.TypeExprFieldRef', with_c : 'vsc_ctxt.TypeConstraint'):
        raise NotImplementedError("mkDataTypeActivityTraverse")

    def findDataTypeComponent(self, name) -> 'DataTypeComponent':
        raise NotImplementedError("findDataTypeComponent")

    def mkDataTypeComponent(self, name) -> 'DataTypeComponent':
        raise NotImplementedError("mkDataTypeComponent")

    def addDataTypeComponent(self, t : 'DataTypeComponent') -> bool:
        raise NotImplementedError("addDataTypeComponent")

    pass