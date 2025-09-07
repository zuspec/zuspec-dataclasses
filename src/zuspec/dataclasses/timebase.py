import abc
from .component import Component
from .decorators import dataclass, input
from .bit import Bit

@dataclass
class TimeBase(object):
    """
    TimeBase exposes the notion of design time
    """

    @abc.abstractmethod
    async def wait(self, amt : float, units):
        """Scales the time to the timebase and waits"""
        pass

    @abc.abstractmethod
    def wait_ev(self, amt : float, units):
        """Scales the time to the timebase and returns an event"""
        pass

    pass

class TimeBaseSignal(TimeBase,Component):
    clock : Bit = input()
    reset : Bit = input()

