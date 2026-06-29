"""Abstract counter — lazy, time-based cycle counter.

Simulation: value is derived lazily from elapsed clock-domain cycles;
no per-cycle callback overhead.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        free_cnt: zdc.Counter = zdc.inst(zdc.Counter)

        @zdc.proc
        async def run(self):
            snap = self.free_cnt.snapshot()
            await self.free_cnt.wait_for(snap + 256)

Lowering
--------
``Counter`` implements the Zuspec interface-dispatch protocols:

* :class:`~zuspec.ir.core.interfaces.Lowerable` — marks Counter as a
  structured-lowering abstraction.
* :class:`~zuspec.ir.core.interfaces.ElaboratableInterface` — ``elaborate_field``
  returns an :class:`~zuspec.ir.core.abstraction_field_ir.AbstractionFieldIR`
  wrapping a :class:`~zuspec.dataclasses.counter_ir.CounterIR` payload.
* :class:`~zuspec.ir.core.interfaces.SVEmittableInterface` — ``rewrite_proc_stmts``
  transforms ``await counter.wait_next()`` to ``await zdc.cycles(PERIOD)``.
* :class:`~zuspec.ir.core.interfaces.SVAEmittableInterface` — provides range-
  invariant and monotone-progress SVA properties.
* :class:`~zuspec.ir.core.interfaces.CSimEmittableInterface` — provides C++
  header and implementation stubs.
"""
from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import Callable, Optional

from .types import SyncComponent, Component
from .decorators import dataclass as _zdcdc, const
from zuspec.be.py.rt.timebase import Timebase


# ---------------------------------------------------------------------------
# Attempt to import lowering protocols (zuspec-ir-core may not be installed)
# ---------------------------------------------------------------------------
try:
    from zuspec.ir.core.interfaces import (
        Lowerable,
        ElaboratableInterface,
        SVEmittableInterface,
        SVAEmittableInterface,
        CSimEmittableInterface,
    )
    from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR
    _INTERFACES_AVAILABLE = True
except ImportError:
    # Graceful degradation: define dummy base classes so the class hierarchy
    # is valid even when zuspec-ir-core is not installed.
    class Lowerable:              pass  # noqa: E701
    class ElaboratableInterface:  pass  # noqa: E701
    class SVEmittableInterface:   pass  # noqa: E701
    class SVAEmittableInterface:  pass  # noqa: E701
    class CSimEmittableInterface: pass  # noqa: E701
    AbstractionFieldIR = None
    _INTERFACES_AVAILABLE = False


@_zdcdc
class Counter(
    SyncComponent,
    Lowerable,
    ElaboratableInterface,
    SVEmittableInterface,
    SVAEmittableInterface,
    CSimEmittableInterface,
):
    """Efficient abstract cycle counter.

    Simulation: :attr:`value` is computed lazily as
    ``(elapsed_cycles - _origin) % modulus`` — no per-cycle interrupt.
    RTL: lowers to a registered accumulator + comparator (handled by
    ``zuspec-be-sw`` / ``zuspec-synth``).

    Parameters
    ----------
    WIDTH:
        Bit width of the counter.  ``modulus == 2**WIDTH``.  Defaults to 32.
    """

    WIDTH: int = const(default=32)

    # _origin and _update_event are NOT dataclass fields — the zdc factory
    # replaces init=False fields with default=None.  We initialise them in
    # __post_init__ via object.__setattr__ so the dataclass machinery and
    # _signal_values flush never touch them.

    def __post_init__(self) -> None:
        super().__post_init__()
        # Initialise mutable state that zdc must not manage.
        if not hasattr(self, '_origin'):
            object.__setattr__(self, '_origin', 0)
        if not hasattr(self, '_update_event'):
            object.__setattr__(self, '_update_event', None)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _period_fs(self) -> int:
        """Clock period in femtoseconds.

        Looks up the most specific clock domain in the component hierarchy that
        has a period set, starting from this Counter and walking up to the root.
        Falls back to 1 ns (1_000_000 fs) when no period is found.
        """
        # Walk the component hierarchy to find a clock domain with a period.
        comp = self
        while comp is not None:
            cd = getattr(type(comp), 'clock_domain', None)
            if cd is not None and cd.period is not None:
                return cd._period_fs()
            # Traverse to parent component.
            try:
                parent = comp._impl._parent if comp._impl is not None else None
            except AttributeError:
                parent = None
            comp = parent
        return 1_000_000  # default: 1 ns

    def _current_cycle(self) -> int:
        """Elapsed cycles since timebase start (or tick() calls in TB mode)."""
        cd = type(self).clock_domain
        # Prefer timebase (pipeline / asyncio.run style):
        try:
            tb = self._impl.timebase()
        except (RuntimeError, AssertionError, AttributeError):
            tb = None
        if tb is not None:
            period_fs = self._period_fs()
            return tb._current_time // period_fs
        # Testbench tick() mode — use _cycle_count on the domain.
        return cd._cycle_count

    def _ensure_update_event(self) -> asyncio.Event:
        """Return (creating if necessary) the asyncio.Event for reset notifications."""
        ev = object.__getattribute__(self, '_update_event')
        if ev is None:
            ev = asyncio.Event()
            object.__setattr__(self, '_update_event', ev)
        return ev

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def modulus(self) -> int:
        """Rollover point: ``2**WIDTH``."""
        return 2 ** self.WIDTH

    @property
    def value(self) -> int:
        """Current counter value (lazy in simulation)."""
        origin = object.__getattribute__(self, '_origin')
        return (self._current_cycle() - origin) % self.modulus

    def snapshot(self) -> int:
        """Alias for :attr:`value`; communicates timestamping intent."""
        return self.value

    def reset(self, v: int = 0) -> None:
        """Set the logical counter value to *v* without stopping simulation.

        ``Counter.value`` will equal *v* immediately after this call.  Any
        coroutines blocked in :meth:`wait_for` (callable variant) will
        recompute their target on the next wake.
        """
        new_origin = self._current_cycle() - (v % self.modulus)
        object.__setattr__(self, '_origin', new_origin)
        # Wake callable wait_for() waiters so they recompute their target.
        ev = object.__getattribute__(self, '_update_event')
        if ev is not None:
            ev.set()
            # Clear on the next iteration so waiters that woke can re-arm.
            asyncio.get_event_loop().call_soon(ev.clear)

    async def wait_for(self, target) -> None:
        """Suspend until the counter reaches *target*.

        *target* may be an ``int`` or a zero-argument callable that returns
        an ``int``.  When a callable is provided the target is re-evaluated
        after every reschedule (e.g. after :meth:`reset` is called).

        Handles rollover transparently.  ``wait_for(v)`` where
        ``v == self.value`` returns immediately.
        """
        if callable(target):
            await self._wait_for_callable(target)
        else:
            await self._wait_for_int(int(target))

    async def _wait_for_int(self, target: int) -> None:
        target = target % self.modulus
        current = self.value
        delta = (target - current) % self.modulus
        if delta == 0:
            return
        period_fs = self._period_fs()
        from .types import Time, TimeUnit
        await self.wait(Time(TimeUnit.FS, delta * period_fs))

    async def _wait_for_callable(self, target_fn: Callable[[], int]) -> None:
        from .types import Time, TimeUnit
        ev = self._ensure_update_event()
        while True:
            target = target_fn() % self.modulus
            current = self.value
            if current == target:
                return
            delta = (target - current) % self.modulus
            period_fs = self._period_fs()

            timer_task = asyncio.create_task(
                self.wait(Time(TimeUnit.FS, delta * period_fs))
            )
            update_task = asyncio.create_task(ev.wait())

            done, pending = await asyncio.wait(
                {timer_task, update_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

            if timer_task in done and target_fn() % self.modulus == target:
                return  # target reached and it hasn't changed

            # reset() fired or target shifted — recompute on next iteration.

    async def wait_ge(self, threshold: int) -> None:
        """Suspend until ``value >= threshold``.

        Handles the case where *threshold* has already been passed in the
        current wrap period by waiting for the next occurrence.
        """
        threshold = threshold % self.modulus
        if self.value >= threshold:
            return
        await self._wait_for_int(threshold)

    async def wait_next(self) -> None:
        """Suspend until the next rollover (``value`` wraps to 0)."""
        current = self.value
        # Wait for the remainder of the current wrap period to reach 0 again.
        # If we're already at 0, wait a full modulus cycles to hit 0 again.
        delta = self.modulus - current if current != 0 else self.modulus
        period_fs = self._period_fs()
        from .types import Time, TimeUnit
        await self.wait(Time(TimeUnit.FS, delta * period_fs))

    def schedule(
        self,
        target: int,
        callback: Callable[[], None],
        *,
        repeat: bool = False,
    ) -> "ScheduleHandle":
        """Register *callback* to fire when the counter reaches *target*.

        Returns a :class:`ScheduleHandle` that supports cancellation and
        rescheduling.

        Parameters
        ----------
        target:
            Counter value at which *callback* fires.
        callback:
            Zero-argument callable invoked when target is reached.
        repeat:
            If ``True`` the schedule fires on every subsequent period at the
            same phase.
        """
        handle = ScheduleHandle(
            counter=self,
            target=int(target) % self.modulus,
            callback=callback,
            repeat=repeat,
        )
        from .spawn import spawn
        spawn(handle._run())
        return handle

    # ── Lowering interface implementations ──────────────────────────────────
    # These classmethods implement the Zuspec interface-dispatch protocols so
    # that Counter is self-describing across all synthesis and formal targets.

    @classmethod
    def elaborate_field(
        cls,
        field_name: str,
        field_index: int,
        inst_kwargs: dict,
        element_type=None,
    ):
        """Build an ``AbstractionFieldIR`` for a ``Counter`` field.

        Reads ``WIDTH`` from *inst_kwargs*; defaults to 32.
        The rollover period is ``2**WIDTH``.
        """
        from .counter_ir import CounterIR
        width = int(inst_kwargs.get("WIDTH", 32))
        period = 1 << width
        ir_node = CounterIR(width=width, period=period, is_free_running=True)
        return AbstractionFieldIR(
            spec_type_name=cls.__name__,
            field_name=field_name,
            field_index=field_index,
            py_cls=cls,
            inst_kwargs=inst_kwargs,
            ir_node=ir_node,
        )

    @classmethod
    def sv_module_text(cls, field_ir) -> str:
        """Counter is inlined into the parent module; no separate module needed."""
        return ""

    @classmethod
    def sv_instance_text(cls, field_ir, parent_prefix: str) -> str:
        """Counter register logic is inlined; no instantiation snippet needed."""
        return ""

    @classmethod
    def rewrite_proc_stmts(cls, stmts: list, field_ir) -> list:
        """Rewrite ``await counter.wait_next()`` → ``await zdc.cycles(PERIOD)``.

        Raises ``NotImplementedError`` for ``wait_for()`` calls, which are not
        synthesisable.
        """
        return _counter_rewrite_stmts(stmts, field_ir.field_index, field_ir.ir_node.period)

    @classmethod
    def sva_assert_properties(cls, field_ir) -> list:
        """Return range-invariant and monotone-progress SVA assert properties."""
        return _counter_sva_properties(field_ir, keyword="assert")

    @classmethod
    def sva_assume_properties(cls, field_ir) -> list:
        """Return range-invariant and monotone-progress SVA assume properties."""
        return _counter_sva_properties(field_ir, keyword="assume")

    @classmethod
    def bmc_depth(cls, field_ir) -> int:
        """Return the counter's period as the minimum BMC depth."""
        return field_ir.ir_node.period

    @classmethod
    def cutpoint_signals(cls, field_ir) -> list:
        """Return the counter signal name as a formal cutpoint."""
        return [field_ir.field_name]

    @classmethod
    def c_header(cls, field_ir) -> str:
        """Return a C++ type declaration for the counter register."""
        w = field_ir.ir_node.width
        uint_t = f"uint{w}_t" if w in (8, 16, 32, 64) else f"uint{w}_t"
        return f"{uint_t} {field_ir.field_name};"

    @classmethod
    def c_impl(cls, field_ir) -> str:
        """Counter C++ implementation is inlined by the codegen backend."""
        return ""


class ScheduleHandle:
    """Opaque handle returned by :meth:`Counter.schedule`.

    Provides cooperative cancellation and one-shot rescheduling.
    """

    def __init__(
        self,
        *,
        counter: Counter,
        target: int,
        callback: Callable[[], None],
        repeat: bool = False,
    ) -> None:
        self._counter = counter
        self._target = target
        self._callback = callback
        self._repeat = repeat
        self._cancelled = False
        self._fired = False

    async def _run(self) -> None:
        while True:
            await self._counter.wait_for(self._target)
            if self._cancelled:
                return
            self._callback()
            self._fired = True
            if not self._repeat:
                return
            # Advance exactly one cycle past the target so the next wait_for()
            # sees delta > 0 and waits a full period rather than returning
            # immediately (delta == 0 is the idempotent "already there" case).
            from .types import Time, TimeUnit
            await self._counter.wait(
                Time(TimeUnit.FS, self._counter._period_fs())
            )

    def cancel(self) -> None:
        """Prevent the callback from firing.

        Safe to call even after the callback has already fired or was
        previously cancelled.
        """
        self._cancelled = True

    def reschedule(self, new_target: int) -> None:
        """Cancel the current schedule and register a new one atomically."""
        self.cancel()
        new_target = int(new_target) % self._counter.modulus
        new_handle = self._counter.schedule(
            new_target, self._callback, repeat=self._repeat
        )
        # Proxy the new handle's state back so callers holding this reference
        # see the updated target and fired status.
        self._cancelled = False
        self._target = new_target
        self._fired = new_handle._fired

    @property
    def fired(self) -> bool:
        """``True`` if the callback has fired at least once."""
        return self._fired


# ---------------------------------------------------------------------------
# Module-level helpers for Counter lowering interfaces
# ---------------------------------------------------------------------------

def _counter_rewrite_stmts(stmts: list, field_index: int, period: int) -> list:
    """Rewrite counter wait calls in a statement list.

    Translates ``await self.<counter>.wait_next()`` to
    ``await zdc.cycles(<period>)``.  Raises ``NotImplementedError`` for
    ``wait_for()`` calls.  Recurses into ``StmtWhile`` and ``StmtIf`` bodies.
    """
    try:
        from zuspec.ir.core.expr import (
            ExprAttribute,
            ExprAwait,
            ExprCall,
            ExprConstant,
            ExprRefUnresolved,
        )
        from zuspec.ir.core.stmt import StmtExpr
    except ImportError:
        return stmts  # zuspec-ir-core not available; return unchanged

    out = []
    for stmt in stmts:
        replaced = _try_rewrite_counter_wait_stmt(
            stmt, field_index, period,
            ExprAttribute, ExprAwait, ExprCall, ExprConstant,
            ExprRefUnresolved, StmtExpr,
        )
        if replaced is not None:
            out.append(replaced)
            continue

        t = type(stmt).__name__
        if t == "StmtWhile":
            new_body = _counter_rewrite_stmts(stmt.body, field_index, period)
            stmt.body.clear()
            stmt.body.extend(new_body)
        elif t == "StmtIf":
            stmt.body[:] = _counter_rewrite_stmts(
                getattr(stmt, "body", []), field_index, period
            )
            stmt.orelse[:] = _counter_rewrite_stmts(
                getattr(stmt, "orelse", []), field_index, period
            )
        out.append(stmt)
    return out


def _try_rewrite_counter_wait_stmt(
    stmt, field_index: int, period: int,
    ExprAttribute, ExprAwait, ExprCall, ExprConstant, ExprRefUnresolved, StmtExpr,
):
    """Return a rewritten statement if *stmt* is a counter-wait call, else ``None``."""
    if type(stmt).__name__ != "StmtExpr":
        return None
    expr = getattr(stmt, "expr", None)
    if type(expr).__name__ != "ExprAwait":
        return None
    call = getattr(expr, "value", None)
    if type(call).__name__ != "ExprCall":
        return None
    func = getattr(call, "func", None)
    if type(func).__name__ != "ExprAttribute":
        return None
    method_name = getattr(func, "attr", None)
    if method_name not in ("wait_next", "wait_for"):
        return None
    field_ref = getattr(func, "value", None)
    if type(field_ref).__name__ != "ExprRefField":
        return None
    if getattr(field_ref, "index", None) != field_index:
        return None

    if method_name == "wait_for":
        raise NotImplementedError(
            "Counter.rewrite_proc_stmts: await counter.wait_for() is not "
            "supported for RTL synthesis. Use wait_next() instead."
        )

    cycles_call = ExprCall(
        func=ExprAttribute(
            value=ExprRefUnresolved(name="zdc"),
            attr="cycles",
        ),
        args=[ExprConstant(value=period)],
        keywords=[],
    )
    return StmtExpr(expr=ExprAwait(value=cycles_call))


def _counter_sva_properties(field_ir, keyword: str) -> list:
    """Return SVA property strings for a Counter field.

    *keyword* is either ``'assert'`` or ``'assume'``.

    Two properties are generated:

    1. **Range invariant** — ``count < period`` (omitted for power-of-two widths
       since it is tautological for the given register width).
    2. **Monotone progress** — counter advances by 1 each cycle and wraps
       correctly.
    """
    sig = field_ir.field_name
    ir = field_ir.ir_node
    m = ir.period
    w = ir.width
    kw = keyword

    props = []

    # Range invariant
    if m != (1 << w):
        props.append(
            f"{kw} property (@(posedge clk) disable iff (!rst_n) "
            f"{sig} < {m});"
        )
    else:
        props.append(
            f"// range_invariant for {sig}: tautological "
            f"(width {w} cannot exceed {m - 1})"
        )

    # Monotone progress (two cases: normal and rollover)
    props.append(
        f"{kw} property (@(posedge clk) disable iff (!rst_n) "
        f"($past({sig}) != {m - 1} |-> {sig} == ($past({sig}) + 1)));\n"
        f"{kw} property (@(posedge clk) disable iff (!rst_n) "
        f"($past({sig}) == {m - 1} |-> {sig} == 0));"
    )

    return props
