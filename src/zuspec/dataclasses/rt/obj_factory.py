from __future__ import annotations
import dataclasses as dc
import inspect
from typing import cast, ClassVar, Dict, List, Type, Optional
from ..config import ObjFactory as ObjFactoryP
from ..types import Component
from .comp_impl_rt import CompImplRT

@dc.dataclass
class ObjFactory(ObjFactoryP):
    comp_type_m : Dict[Type[Component],Type[Component]] = dc.field(default_factory=dict)
    comp_s : List[Component] = dc.field(default_factory=list)
    _inst : ClassVar = None

    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = ObjFactory()
        return cls._inst

    def mkComponent(self, cls : Type[Component], **kwargs) -> Component:
        print("mkComponent: %s" % cls.__qualname__)
        if cls in self.comp_type_m.keys():
            cls_rt = self.comp_type_m[cls]
        else:
            fields = []
            namespace = {}

#            if "__post_init__" in cls.__dict__.keys():
#                namespace["__post_init__"] = cls.__dict__["__post_init__"]

            for f in dc.fields(cls):
                print("Src Field: %s" % f.name)
                if inspect.isclass(f.type):
                    if issubclass(f.type, Component):
                        print("Component instance")
                        # Re-author to ensure construction is proper
            # TODO: Copy over 

            cls_rt = dc.make_dataclass(
                cls.__name__,
                fields,
                namespace=namespace,
                kw_only=True,
                bases=(cls,))
            self.comp_type_m[cls] = cls_rt


        setattr(cls_rt, "__dc_init__", getattr(cls_rt, "__init__"))
        setattr(cls_rt, "__init__", self.__comp_init__)

        # Just a placeholder at this point
        kwargs["_impl"] = None

        comp = Component.__new__(cls_rt, **kwargs)
        
        return cast(Component, comp)

    @staticmethod 
    def __comp_init__(comp, *args, **kwargs):
        self = ObjFactory.inst()
        print("--> comp_init__ %d" % len(self.comp_s))
            
        self.comp_s.append(comp)
        getattr(comp, "__dc_init__")(comp, *args, **kwargs)
        self.comp_s.pop()

        if len(self.comp_s) == 0:
            # Initialize the component tree after initialization
            # of the root component
            impl = CompImplRT(_factory=self, _name="", _parent=None)

        print("<-- __comp_init__ %d" % len(self.comp_s))


    pass

