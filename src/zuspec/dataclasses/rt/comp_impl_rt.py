from __future__ import annotations
import dataclasses as dc
import inspect
from typing import TYPE_CHECKING, Optional
from ..types import Component

if TYPE_CHECKING:
    from .obj_factory import ObjFactory


@dc.dataclass(kw_only=True)
class CompImplRT(object):
    _factory : ObjFactory = dc.field()
    _name : str = dc.field()
    _parent : Component = dc.field()

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parent(self) -> Component:
        return self._parent

    def post_init(self, comp):
        from .obj_factory import ObjFactory
        print("--> CompImpl.post_init")

        for f in dc.fields(comp):
            fo = getattr(comp, f.name)

            if inspect.isclass(f.type) and issubclass(f.type, Component): # and not f.init:
                print("Comp Field: %s" % f.name)
                if hasattr(fo, "_impl"):
                    fo._impl.post_init(fo)
                    print("Has impl")
                pass
        print("<-- CompImpl.post_init")

#        self.name = self.factory.name_s[-1]

    def build(self, factory):
        pass

    async def wait(self, amt : float, units : int=0):
        print("wait")

    pass