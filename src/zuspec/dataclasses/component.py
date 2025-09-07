import abc
from typing import TYPE_CHECKING
from .decorators import dataclass, field
from .struct import Struct

if TYPE_CHECKING:
    from .timebase import TimeBase

@dataclass
class Component(Struct):
    """
    Component classes are structural in nature. 
    The lifecycle of a component tree is as follows:
    - The root component and fields of component type are constructed
    - The 'init_down' method is invoked in a depth-first manner
    - The 'init_up' method is invoked
    """
#    timebase : 'TimeBase' = field()

    def build(self): pass

    @abc.abstractmethod
    async def wait(self, amt : float, units):
        pass

    @abc.abstractmethod
    async def wait_next(self, count : int = 1):
        pass


