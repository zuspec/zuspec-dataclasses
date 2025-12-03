from __future__ import annotations
import dataclasses as dc
from typing import ClassVar, Optional, Protocol, Type
from .types import Component

class ObjFactory(Protocol):

    def mkComponent(self, cls : Type[Component], **kwargs) -> Component: ...

@dc.dataclass
class Config(object):
    _factory : Optional[ObjFactory] = dc.field(default=None)
    _inst : ClassVar[Optional[Config]] = None

    def __post_init__(self):
        from .rt import ObjFactory
        self._factory = ObjFactory()
        pass

    @property
    def factory(self)-> ObjFactory:
        assert self._factory is not None
        return self._factory
    
    @factory.setter
    def factory(self, f : ObjFactory):
        self._factory = f

    @classmethod
    def inst(cls) -> Config:
        if cls._inst is None:
            cls._inst = Config()
        return cls._inst

