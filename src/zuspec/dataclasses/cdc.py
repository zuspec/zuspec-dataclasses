"""Clock-domain crossing (CDC) primitives for zuspec.

Provides:

- :class:`TwoFFSync` — synthesizable two-flip-flop synchronizer for slow
  single-bit signals.
- :class:`AsyncFIFO` — placeholder for a multi-bit asynchronous FIFO.
- :func:`cdc_unchecked` — suppression decorator/marker that tells the CDC
  analysis pass to ignore a known-safe crossing.

Usage example::

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Sys(zdc.Component):
        fast_to_slow : zdc.TwoFFSync = zdc.inst()

    # Suppress a crossing you know is safe by design
    @zdc.cdc_unchecked("Gray-coded counter, safe by design")
    class GraySync(zdc.Component):
        ...
"""

from __future__ import annotations

import dataclasses as _dc
from typing import ClassVar, Optional

import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# TwoFFSync
# ---------------------------------------------------------------------------

@zdc.dataclass
class TwoFFSync(zdc.Component):
    """Two-flip-flop synchronizer for single-bit CDC crossings.

    Registers ``data_in`` (captured in the *source* domain) through two
    flip-flops clocked by the *destination* domain clock.  This breaks the
    metastability chain with high probability.

    The synthesizer emits a ``set_false_path`` SDC constraint from the
    source clock to the first register stage (``_sync0_reg``) so timing
    tools know the launch/capture relationship is intentionally asynchronous.

    Class attributes:
        src_domain: Name of the source clock domain (string).  Set this on a
            subclass or instance to drive SDC generation.
        dst_domain: Name of the destination clock domain (string).
    """

    # ClassVar attributes are excluded from dataclass field processing.
    # Users may override on a subclass to name the domains explicitly.
    src_domain: ClassVar[Optional[str]] = None
    dst_domain: ClassVar[Optional[str]] = None

    # Marker used by CDC analysis and synthesizer to identify this primitive.
    _zdc_two_ff_sync: ClassVar[bool] = True

    data_in  : zdc.bit = zdc.input()
    data_out : zdc.bit = zdc.output(reset=0)
    _sync0   : zdc.bit = zdc.reg(reset=0)

    @zdc.sync
    def _shift(self):
        self._sync0  = self.data_in
        self.data_out = self._sync0


# ---------------------------------------------------------------------------
# AsyncFIFO  (structural placeholder)
# ---------------------------------------------------------------------------

@zdc.dataclass
class AsyncFIFO(zdc.Component):
    """Asynchronous FIFO for multi-bit CDC crossings (structural placeholder).

    This class documents the intended interface.  Full synthesizable output
    is deferred to a future phase.

    Ports:
        wr_clk / wr_rst_n — write-side clock/reset.
        rd_clk / rd_rst_n — read-side clock/reset.
        data_in / wr_en   — write datapath.
        data_out / rd_en  — read datapath.
        full / empty      — flow-control flags.
    """

    # ClassVar: not dataclass fields.
    src_domain: ClassVar[Optional[str]] = None
    dst_domain: ClassVar[Optional[str]] = None

    data_in  : zdc.b32 = zdc.input()
    wr_en    : zdc.bit = zdc.input()
    data_out : zdc.b32 = zdc.output(reset=0)
    rd_en    : zdc.bit = zdc.input()
    full     : zdc.bit = zdc.output(reset=0)
    empty    : zdc.bit = zdc.output(reset=1)


# ---------------------------------------------------------------------------
# cdc_unchecked decorator
# ---------------------------------------------------------------------------

def cdc_unchecked(reason: str = ""):
    """Mark a class or field as a known-safe CDC crossing.

    When applied to a :class:`~zuspec.dataclasses.Component` subclass the
    CDC analysis pass will skip any crossings that involve an instance of
    that class.

    When applied to a Python dataclass *field* that holds a sub-component
    instance (declared with :func:`~zuspec.dataclasses.inst`) the analysis
    pass will suppress the crossing attributed to that specific instance.

    :param reason: Human-readable explanation of why the crossing is safe.
                   Required for auditability.

    Usage::

        @zdc.cdc_unchecked("Gray-coded counter — safe by construction")
        @zdc.dataclass
        class GraySyncBus(zdc.Component): ...

        # On a sub-instance field:
        my_bridge : GraySyncBus = zdc.cdc_unchecked("safe")(zdc.inst())
    """
    if not reason:
        raise ValueError("cdc_unchecked() requires a non-empty 'reason' string.")

    def _decorator(target):
        if isinstance(target, type):
            # Applied to a class
            target._cdc_unchecked = True
            target._cdc_unchecked_reason = reason
            return target
        else:
            # Applied to a field default (e.g. the result of zdc.inst())
            # Store as attributes on the default object.
            try:
                target._cdc_unchecked = True
                target._cdc_unchecked_reason = reason
            except (AttributeError, TypeError):
                pass
            return target

    return _decorator
