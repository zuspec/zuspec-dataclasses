"""CounterIR — elaboration-time IR payload for Counter abstraction fields.

Produced by ``Counter.elaborate_field()`` and stored as the ``ir_node``
inside an :class:`~zuspec.ir.core.abstraction_field_ir.AbstractionFieldIR`.
Consumed by ``AbstractionSVLowerPass`` and ``AbstractionFormalPass``.
"""

from dataclasses import dataclass


@dataclass
class CounterIR:
    """Synthesisable parameters extracted from a Counter field at elaboration time.

    Attributes
    ----------
    width : int
        Bit width of the counter register.
    period : int
        Rollover modulus.  For a plain ``Counter`` this is ``2**width``.
        For a ``ModuloCounter`` or ``WatchdogCounter`` it equals ``PERIOD``
        or ``TIMEOUT`` respectively.
    is_free_running : bool
        ``True`` for free-running counters (``Counter``, ``ModuloCounter``).
        ``False`` for watchdog counters that reset on an external event.
    """

    width: int
    period: int
    is_free_running: bool = True
