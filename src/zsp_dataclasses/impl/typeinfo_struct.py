
from .type_info import TypeInfo

class TypeInfoStruct(TypeInfo):

    def __init__(self, info):
        super().__init__(info)

    @staticmethod
    def get(info):
        if not hasattr(info, TypeInfo.ATTR_NAME):
            setattr(info, TypeInfo.ATTR_NAME, TypeInfoStruct(info))
        return getattr(info, TypeInfo.ATTR_NAME)
