from __future__ import annotations
import dataclasses as dc
from typing import ClassVar, List, Optional, Protocol, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Event

from .types import Component, Timebase

class ObjFactory(Protocol):

    def mkComponent(self, cls : Type[Component], **kwargs) -> Component: ...
    
    def mkEvent(self, cls : Type['Event'], **kwargs) -> 'Event': ...

@dc.dataclass
class Config(object):
    _factory_s : List[ObjFactory] = dc.field(default_factory=list)
    _timebase_s : List[Timebase] = dc.field(default_factory=list)
    _inst : ClassVar[Optional[Config]] = None

    def __post_init__(self):
        from .rt import ObjFactory, Timebase
        self._factory_s.append(ObjFactory.inst())
        self._timebase_s.append(Timebase())
        pass

    @property
    def factory(self)-> ObjFactory:
        assert len(self._factory_s) > 0
        return self._factory_s[-1]

    def push_factory(self, f : ObjFactory):
        self._factory_s.append(f)

    def pop_factory(self):
        self._factory_s.pop()    

    @classmethod
    def inst(cls) -> Config:
        if cls._inst is None:
            cls._inst = Config()
        return cls._inst

