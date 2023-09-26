
from enum import IntEnum, auto
from tokenize import Intnumber
from typing import List
import vsc_dataclasses as vsc

import vsc_dataclasses.impl.context as vsc_ctxt

class DataTypeArlStruct(vsc_ctxt.DataTypeStruct):

    def addExec(self, exec : 'TypeExec'):
        raise NotImplementedError("addExec")
    
    def getExecs(self):
        raise NotImplementedError("getExecs")
    
    def addFunction(self, f : 'DataTypeFunction'):
        raise NotImplementedError("addFunction")
    
    def getFunctions(self):
        raise NotImplementedError("getFunctions")


class DataTypeAction(DataTypeArlStruct):

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

class DataTypeActivity(vsc_ctxt.DataType):

    def mkActivity(self, ctxt : vsc_ctxt.ModelBuildContext, type : 'TypeFieldActivity'):
        raise NotImplementedError("mkActivity")


class DataTypeActivityScope(DataTypeActivity, vsc_ctxt.DataTypeStruct):

    def getActivities(self) -> List['TypeFieldActivity']:
        raise NotImplementedError("getActivities")

    def addActivity(self, a : 'TypeFieldActivity'):
        raise NotImplementedError("addActivity")
    
    def addActivityField(self, a : 'TypeFieldActivity'):
        raise NotImplementedError("addActivityField")

class DataTypeActivityReplicate(DataTypeActivityScope):

    def getCount(self) -> 'TypeExpr':
        pass

class DataTypeActivityTraverse(DataTypeActivity):

    def getTarget(self) -> vsc_ctxt.TypeExprFieldRef:
        raise NotImplementedError("getTarget")

    def getWithC(self) -> 'vsc_ctxt.TypeConstraint':
        raise NotImplementedError("getWithC")

    def setWithC(self, c : 'vsc_ctxt.TypeConstraint'):
        raise NotImplementedError("setWithC")


class DataTypeComponent(vsc_ctxt.DataTypeStruct):

    def getActionTypes(self) -> List[DataTypeAction]:
        raise NotImplementedError("getActionTypes")

    def addActionType(self, t : DataTypeAction):
        raise NotImplementedError("addActionType")

    def addPoolBindDirective(self, bind : 'PoolBindDirective'):
        raise NotImplementedError("addPoolBindDirective")
    
class ParamDir(IntEnum):
    In = auto()
    Out = auto()
    InOut = auto()

class TypeProcStmtVarDecl(object):

    def name(self) -> str:
        raise NotImplementedError("name")
    
    def getDataType(self) -> vsc_ctxt.DataType:
        raise NotImplementedError("getDataType")
    
    def getInit(self):
        raise NotImplementedError("getInit")
    
class DataTypeFunctionParamDecl(TypeProcStmtVarDecl):
    def getDirection(self) -> ParamDir:
        raise NotImplementedError("getDirection")
    
class DataTypeFunction(vsc_ctxt.DataType):

    def name(self):
        raise NotImplementedError("DataTypeFunction.name")
    
    def getReturnType(self) -> vsc_ctxt.DataType:
        raise NotImplementedError("DataTypeFunction.getReturnType")
    
    def getParameters(self) -> List[DataTypeFunctionParamDecl]:
        raise NotImplementedError("DataTypeFunction.getParameters")
    
    def addParameter(self, p : DataTypeFunctionParamDecl):
        raise NotImplementedError("DataTypeFunction.addParameter")


class FlowObjKindE(IntEnum):
    Buffer   = 0
    Resource = 1
    State    = 2
    Stream   = 3

class ModelBuildContext(vsc_ctxt.ModelBuildContext):

    def __init__(self, ctxt):
        super().__init__(ctxt)
    pass

class ModelEvalNodeT(IntEnum):
    Action = 0

class ModelFieldComponent(vsc_ctxt.ModelField):

    def initCompTree(self):
        raise NotImplementedError("initCompTree")


class PoolBindKind(IntEnum):
    All = 0

class TypeFieldActivity(vsc_ctxt.TypeField):

    def mkActivity(self, ctxt : ModelBuildContext):
        raise NotImplementedError("mkActivity")

class Context(vsc.impl.Context):

    def findDataTypeAction(self, name) -> 'DataTypeAction':
        raise NotImplementedError("findDataTypeAction")
    
    def mkDataTypeAction(self, name) -> DataTypeAction:
        raise NotImplementedError("mkDataTypeAction")

    def addDataTypeAction(self, t : DataTypeAction) -> bool:
        raise NotImplementedError("addDataTypeAction")

    def mkDataTypeActivityParallel(self) -> 'DataTypeActivityParallel':
        raise NotImplementedError("mkDataTypeActivityParallel")

    def mkDataTypeActivityReplicate(self, count) -> 'DataTypeActivityReplicate':
        raise NotImplementedError("mkDataTypeActivityReplicate")

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
    
    def mkDataTypeFunction(self,
                           name : str,
                           rtype : vsc_ctxt.DataType,
                           own_rtype : bool,
                           is_target : bool,
                           is_solve : bool):
        raise NotImplementedError("mkDataTypeFunction")

    def mkDataTypeFunctionParamDecl(self,
                                name,
                                dir : ParamDir,
                                type : vsc_ctxt.DataType,
                                own : bool,
                                init : vsc_ctxt.TypeExpr) -> DataTypeFunctionParamDecl:
        raise NotImplementedError("mkDataTypeFunctionParamDecl")


    def mkTypeFieldActivity(self, name, type : 'DataTypeActivity', owned):
        raise NotImplementedError("mkTypeFieldActivity")
    

    pass