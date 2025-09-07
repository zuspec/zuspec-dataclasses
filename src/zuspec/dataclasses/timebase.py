import abc
from typing import TYPE_CHECKING
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
    async def wait_next(self, count : int = 1):
        """Waits for 'count' timebase events (eg clocks)"""
        pass

    @abc.abstractmethod
    def wait_ev(self, amt : float, units):
        """Scales the time to the timebase and returns an event"""
        pass

    pass

#class TimeBaseSignal(TimeBase,Component):
#    clock : Bit = input()
#    reset : Bit = input()

