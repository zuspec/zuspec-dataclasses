
import abc
from .component import Component
from .decorators import dataclass, field, output
from .bit import Bit

@dataclass
class ClockReset(Component):
    period : int = field(default=10)
    clock : Bit = output()
    reset : Bit = output()

    @abc.abstractmethod
    def assert_reset(self): pass

    @abc.abstractmethod
    def release_reset(self): pass

    @abc.abstractmethod
    async def next(self, count : int = 1):
        pass
