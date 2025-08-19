from .decorators import dataclass

@dataclass
class Struct(object):

    # def __new__(cls, *args, **kwargs):
    #     cls_p = None
    #     print("cls: %s %s" % (str(cls), getattr(cls, "__xform__", False)))

    #     if not getattr(cls, "__xform__", False):
    #         # Determine whether to replace
    #         cls_p = TypeTransformerDefault.inst().transform(cls)
    #         print("cls_p: %s ; xform: %s" % (cls_p, getattr(cls_p, "__xform__", False)))

    #     if cls_p is not None:
    #         # The default transformer wants to replace the class
    #         print("Constructing override class %s" % cls)
    #         print("--> cls_p")
    #         s = cls_p.__new__(cls_p, *args, **kwargs)
    #         print("<-- cls_p")
    #     else:
    #         print("Constructing base class %s" % cls)
    #         s = super().__new__(cls, *args, **kwargs)
    #     print("-- return %d" % id(s))
    #     return s

    pass

# @dataclass
# class StructP(object):

#     def __post_init__(self):
#         print("StructP.__post_init__")