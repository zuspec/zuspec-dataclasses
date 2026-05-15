"""BusPort abstract base class."""
from __future__ import annotations
from abc import ABC, abstractmethod


class BusPort(ABC):
    """Abstract base class for bus protocol adapters.

    Subclasses implement the physical bus protocol and call
    :meth:`~.base.RegisterFile.bus_write` / :meth:`~.base.RegisterFile.bus_read`
    on the bound register file.
    """

    @abstractmethod
    def bind(self, regfile) -> None:
        """Bind this port to a :class:`~.base.RegisterFile` instance."""
        ...
