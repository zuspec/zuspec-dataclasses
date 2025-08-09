
from .flow_obj_kind_e import FlowObjKindE
from .type_info import TypeInfo


class TypeInfoFlowObj(TypeInfo):

    def __init__(self, info, kind : FlowObjKindE):
        super().__init__(info)
        self.kind = kind

    @staticmethod
    def get(info, kind) -> 'TypeInfoFlowObj':
        if not hasattr(info, TypeInfo.ATTR_NAME):
            setattr(info, TypeInfo.ATTR_NAME, TypeInfoFlowObj(kind))
        return getattr(info, TypeInfo.ATTR_NAME)
