from __future__ import annotations
import logging
from typing import ClassVar, Dict, Type, Self, TYPE_CHECKING

from .base import Base

class Visitor:
    _type_impl_m : Dict[Type[Visitor],Type[Visitor]] = {}
    _log : ClassVar = logging.getLogger("zuspec.ir.Visitor")

    def __new__(cls, pmod) -> Visitor:
        if pmod is None:
            return super().__new__(cls)
        elif cls in Visitor._type_impl_m.keys():
            return Visitor._type_impl_m[cls].__new__(cls, pmod)
        else:
            # Build out the implementation
            # Need a visitor for each Base-derived 
            # object
            #
            # If this class doesn't provide one, add an 
            # implementation that redirects to visitBase
            #
            # Create a class that implements any 
            from .profile_rgy import ProfileRgy
            fields = {}
            profile = ProfileRgy.get_profile(pmod)
            for t in profile.types:
                if hasattr(cls, "visit%s" % t.__name__):
                    print("Class has %s" % t.__name__)
                    fields["visit%s" % t.__name__] = getattr(cls, "visit%s" % t.__name__)
                else:
                    print("Must define %s" % t.__name__)
                    fields["visit%s" % t.__name__] = lambda self,o,cls=t: Visitor.visitDefault(self, o, t)

            fields["__new__"] = lambda cls,pmod=None: super().__new__(cls)

            impl : Type[Visitor] = type(
                cls.__qualname__, 
                (cls,), 
                fields)

            print("impl: %s" % str(impl))
            print("cls: %s" % str(cls))
            Visitor._type_impl_m[cls] = impl

            return impl(None)
        
    @staticmethod
    def visitDefault(self : Visitor, obj : Base, cls : Type):
        self._log.debug("--> visitDefault virt=%s" % cls.__name__)
        if type(self) == cls:
            obj.accept(self)
        else:
            obj.visitDefault(self, cls)
        self._log.debug("<-- visitDefault virt=%s" % cls.__name__)

        
    # def __init__(self, pmod):
    #     pass

    def visitBase(self, o : Base):
        o.visitDefault(self)
        pass


