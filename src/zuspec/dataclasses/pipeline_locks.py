"""Pipeline hazard lock strategy classes.

Each lock strategy controls how RAW (read-after-write) hazards are resolved
for a :class:`~zuspec.dataclasses.pipeline_resource.PipelineResource`.

Strategies
----------
:class:`QueueLock`
    FIFO-ordered stall lock.  No bypass.  Readers block until all previous
    writers have committed.

:class:`BypassLock`
    In-order lock with bypass network.  ``write()`` forwards the value to
    blocked readers without waiting for write-back.

:class:`RenameLock`
    Tomasulo-style rename lock for out-of-order execution.
"""

from __future__ import annotations


class HazardLock:
    """Base class for pipeline hazard lock strategies.

    Concrete subclasses override the rt methods (``reserve``, ``block``,
    ``write``, ``release``).  The base class methods are stubs — the
    ``rt`` layer injects full implementations at simulation time.
    """


class QueueLock(HazardLock):
    """FIFO-ordered stall lock; no bypass.

    One FIFO entry per outstanding writer per address.  Readers block until
    all preceding writers have called :meth:`release`.

    This is the default lock when none is specified.
    """

    def __init__(self) -> None:
        pass


class BypassLock(HazardLock):
    """In-order lock with bypass network.

    ``write()`` immediately forwards the value to all blocked readers via a
    bypass bus.  The latency between ``write()`` and when the value reaches
    the reader is ``bypass_latency`` cycles (default 1 — same cycle).

    Args:
        bypass_latency: Cycles from ``write()`` to value availability.
    """

    def __init__(self, *, bypass_latency: int = 1) -> None:
        self.bypass_latency = bypass_latency


class RenameLock(HazardLock):
    """Tomasulo-style rename lock for out-of-order execution.

    Each write allocates a physical register from a pool of *phys_regs*
    entries.  Readers are bound to the physical register at issue time,
    enabling out-of-order completion without WAR/WAW hazards.

    Args:
        phys_regs: Size of the physical register file (rename pool).
    """

    def __init__(self, *, phys_regs: int) -> None:
        self.phys_regs = phys_regs
