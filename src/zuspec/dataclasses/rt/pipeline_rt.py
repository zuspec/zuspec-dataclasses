"""Full ``rt`` execution engine for the async pipeline behavioral model.

This module implements the runtime components that back the
``@zdc.pipeline`` async DSL:

* :class:`_SlotTable` — per-stage structural availability tracking
* :class:`PipelineToken` — per-transaction metadata and snapshots
* :class:`PipelineTrace` — event log and observer dispatch
* :class:`PipelineStage` — async context manager with cycle accounting
* :class:`PipelineRuntime` — top-level runtime state per pipeline process
"""

from __future__ import annotations

import asyncio
import dataclasses as dc
from collections import defaultdict
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional

# Import all shared ContextVars from pipeline_ns.
from ..pipeline_ns import (
    _PIPELINE_RT,
    _CURRENT_TOKEN,
    _CURRENT_STAGE_IDX,
    _CURRENT_STAGE,
)


# ---------------------------------------------------------------------------
# _SlotTable
# ---------------------------------------------------------------------------

class _SlotTable:
    """Per-stage earliest-available cycle tracker.

    Enforces structural hazards: a token cannot enter a stage until the
    previous token has exited.  All mutations are synchronous (no ``await``)
    so they are effectively atomic in asyncio's single-threaded model.
    """

    def __init__(self) -> None:
        self._free_at: Dict[int, int] = {}

    def reserve_slot(self, stage_idx: int, token_arrives: int,
                     nominal_cycles: int) -> int:
        """Compute entry cycle and immediately mark the slot busy.

        Because there is no ``await`` between computing the entry cycle and
        marking the slot, concurrent token tasks cannot observe an
        inconsistent state.

        Args:
            stage_idx:      Zero-based stage index.
            token_arrives:  Cycle at which the token would like to enter.
            nominal_cycles: Minimum cycle count for this stage.

        Returns:
            Actual entry cycle (>= token_arrives).
        """
        enter = max(token_arrives, self._free_at.get(stage_idx, 0))
        self._free_at[stage_idx] = enter + nominal_cycles
        return enter

    def extend_slot(self, stage_idx: int, enter: int, nominal_cycles: int,
                    extra: int) -> int:
        """Extend slot occupancy after additional stall cycles are known.

        Only ever increases ``_free_at``; never shrinks it.

        Args:
            stage_idx:      Zero-based stage index.
            enter:          Cycle the token entered this stage.
            nominal_cycles: Original stage cycle count.
            extra:          Additional stall cycles accumulated so far.

        Returns:
            Exit cycle (last cycle the stage is occupied).
        """
        exit_cycle = enter + nominal_cycles - 1 + extra
        new_free = exit_cycle + 1
        if new_free > self._free_at.get(stage_idx, 0):
            self._free_at[stage_idx] = new_free
        return exit_cycle


# ---------------------------------------------------------------------------
# PipelineToken
# ---------------------------------------------------------------------------

@dc.dataclass
class PipelineToken:
    """One pipeline transaction — metadata and per-stage snapshots.

    Attributes:
        token_id:        Monotonically-increasing identifier.
        cycle:           Current simulated cycle position for this token.
                         Advanced at each stage exit and by auto-stall.
        stage_snapshots: Mapping from stage index to ``{varname: value}`` dict
                         captured at stage exit.
        enter_cycles:    Mapping from stage index to the cycle the token entered.
        exit_cycles:     Mapping from stage index to the cycle the token exited.
        valid:           ``False`` if :meth:`PipelineStage.bubble` was called.
        extra_stall:     Accumulated stall cycles requested by the pipeline body.
    """
    token_id: int
    cycle: int                           = 0
    stage_snapshots: Dict[int, dict]     = dc.field(default_factory=dict)
    enter_cycles: Dict[int, int]         = dc.field(default_factory=dict)
    exit_cycles: Dict[int, int]          = dc.field(default_factory=dict)
    valid: bool = True
    extra_stall: int = 0


# ---------------------------------------------------------------------------
# PipelineTrace
# ---------------------------------------------------------------------------

class PipelineTrace:
    """Sparse record of token lifecycle events.

    Observers receive ``(token, event_name, **kwargs)`` calls synchronously
    on each event.

    Events:  ``"stage_enter"``, ``"stage_exit"``, ``"stall"``,
             ``"bubble"``, ``"token_complete"``.
    """

    def __init__(self) -> None:
        self._tokens: List[PipelineToken] = []
        self._observers: List[Callable] = []

    def add_token(self, token: PipelineToken) -> None:
        self._tokens.append(token)

    def record(self, token: PipelineToken, event: str, **kw) -> None:
        """Dispatch *event* to all registered observers."""
        for cb in self._observers:
            cb(token, event, **kw)

    def add_observer(self, cb: Callable) -> None:
        """Register a callback ``(token, event, **kw) -> None``."""
        self._observers.append(cb)

    def tokens(self) -> List[PipelineToken]:
        """Return a copy of the token list."""
        return list(self._tokens)

    def print_trace(self, *, file=None) -> None:
        """Print a human-readable Gantt-style pipeline trace."""
        import sys
        out = file or sys.stdout
        if not self._tokens:
            print("<no pipeline tokens>", file=out)
            return
        # Determine max stage index across all tokens
        max_stage = max(
            (max(t.enter_cycles.keys(), default=-1) for t in self._tokens),
            default=-1,
        )
        if max_stage < 0:
            print("<no stages recorded>", file=out)
            return
        # Header
        stage_width = 6
        header = f"{'Tok':>4} " + " ".join(f"S{i:<{stage_width-1}}" for i in range(max_stage + 1))
        print(header, file=out)
        print("-" * len(header), file=out)
        for tok in self._tokens:
            row = f"{tok.token_id:>4} "
            cells = []
            for i in range(max_stage + 1):
                enter = tok.enter_cycles.get(i, None)
                exit_ = tok.exit_cycles.get(i, None)
                if enter is not None and exit_ is not None:
                    cells.append(f"{enter}-{exit_}".ljust(stage_width))
                else:
                    cells.append(" " * stage_width)
            row += " ".join(cells)
            if not tok.valid:
                row += "  [bubble]"
            print(row, file=out)


# ---------------------------------------------------------------------------
# PipelineStage  (rt-active _StageHandle replacement)
# ---------------------------------------------------------------------------

class PipelineStage:
    """rt-active stage handle; replaces :class:`~..pipeline_ns._StageHandle`.

    Returned by :meth:`PipelineRuntime.stage_handle` when a pipeline
    coroutine is executing inside the rt engine.  Implements the same
    async context-manager interface as ``_StageHandle`` with full cycle
    accounting.

    Each stage atomically reserves its slot in ``_SlotTable`` at ``__aenter__``
    time — no ``await`` occurs between the slot reservation and the entry
    cycle being committed, so concurrent token tasks cannot observe an
    inconsistent view.
    """

    def __init__(
        self,
        runtime: "PipelineRuntime",
        stage_idx: int,
        cycles: int,
        token: PipelineToken,
        timebase,
    ) -> None:
        self._rt = runtime
        self._stage_idx = stage_idx
        self._cycles = cycles
        self._token = token
        self._tb = timebase
        self._extra = 0
        self._bubble_called = False
        self._enter = 0          # set in __aenter__
        self._stage_ctx = None   # ContextVar token for _CURRENT_STAGE

    async def __aenter__(self) -> "PipelineStage":
        tok = self._token
        # Reserve slot atomically (synchronous — no await before this)
        self._enter = self._rt._slots.reserve_slot(
            self._stage_idx, tok.cycle, self._cycles
        )
        stall_wait = self._enter - tok.cycle
        if stall_wait > 0:
            await self._tb.wait_cycles(stall_wait, self._rt._domain)
        tok.cycle = self._enter
        tok.enter_cycles[self._stage_idx] = self._enter
        # Expose this stage as the active one for auto-stall
        self._stage_ctx = _CURRENT_STAGE.set(self)
        self._rt._trace.record(tok, "stage_enter", stage=self._stage_idx)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        tok = self._token
        exit_c = self._rt._slots.extend_slot(
            self._stage_idx, self._enter, self._cycles, self._extra
        )
        # Skip the timing wait if an exception is propagating (including
        # CancelledError at simulation end).  The timebase may have already
        # stopped; blocking on wait_cycles would deadlock.
        if exc_type is None:
            # Compute remaining cycles to wait, accounting for time already
            # consumed by block() stalls (auto-stall advanced tok.cycle).
            next_c = exit_c + 1          # cycle when next stage may enter
            cycles_remaining = next_c - tok.cycle
            if cycles_remaining > 0:
                await self._tb.wait_cycles(cycles_remaining, self._rt._domain)
            tok.cycle = next_c
        tok.exit_cycles[self._stage_idx] = exit_c
        _CURRENT_STAGE.reset(self._stage_ctx)
        if exc_type is None:
            self._rt._trace.record(tok, "stage_exit", stage=self._stage_idx)
            if self._bubble_called:
                self._rt._trace.record(tok, "bubble", stage=self._stage_idx)
        return False

    async def stall(self, n: int = 1) -> None:
        """Extend this stage's occupancy by *n* additional cycles.

        Useful when a functional unit needs more time (e.g. a multi-cycle
        multiplier).  Subsequent tokens entering this stage will be held off
        by the :class:`_SlotTable` for the extra cycles.  The ``"stall"``
        event is dispatched to all registered trace observers.

        Args:
            n: Extra cycles to add (default 1).
        """
        self._extra += n
        self._token.extra_stall += n
        self._rt._slots.extend_slot(
            self._stage_idx, self._enter, self._cycles, self._extra
        )
        self._rt._trace.record(self._token, "stall", stage=self._stage_idx, n=n)

    async def bubble(self) -> None:
        """Invalidate this token; slot drains without producing side effects.

        Sets :attr:`valid` to ``False`` on the token.  The pipeline method
        body continues executing (remaining stages run), but downstream
        logic can inspect ``ST.valid`` to skip writes and releases.  A
        ``"bubble"`` event is dispatched at stage exit.
        """
        self._token.valid = False
        self._bubble_called = True

    @property
    def cycle(self) -> int:
        """Cycle at which this token entered the stage."""
        return self._token.enter_cycles.get(self._stage_idx, 0)

    @property
    def valid(self) -> bool:
        """False if :meth:`bubble` has been called."""
        return self._token.valid


# ---------------------------------------------------------------------------
# PipelineRuntime
# ---------------------------------------------------------------------------

class PipelineRuntime:
    """Top-level rt state; one instance per pipeline process invocation.

    Maintains the :class:`_SlotTable`, :class:`PipelineTrace`, and
    per-token accounting.  Also holds the mapping from
    :class:`~..pipeline_resource.PipelineResource` instances to their
    rt lock implementations.

    Token tasks run concurrently (one per cycle); per-token state
    (:class:`PipelineToken`, stage-index counter, active stage) is carried
    via ContextVars so each asyncio task has its own view.
    """

    def __init__(self, comp, domain, timebase) -> None:
        self._comp = comp
        self._domain = domain
        self._timebase = timebase
        self._slots = _SlotTable()
        self._trace = PipelineTrace()
        self._cycle: int = 0          # issuer's cycle counter
        self._token_id: int = 0
        self._in_flight: List[PipelineToken] = []
        self._lock_rts: Dict[int, Any] = {}

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def new_token(self) -> PipelineToken:
        tok = PipelineToken(token_id=self._token_id)
        self._token_id += 1
        self._in_flight.append(tok)
        self._trace.add_token(tok)
        return tok

    def _complete_token(self, tok: PipelineToken) -> None:
        self._trace.record(tok, "token_complete")
        if tok in self._in_flight:
            self._in_flight.remove(tok)

    # ------------------------------------------------------------------
    # Stage handle factory — called from pipeline body tasks
    # ------------------------------------------------------------------

    def stage_handle(self, cycles: int) -> PipelineStage:
        """Return a :class:`PipelineStage` for the next stage index.

        Reads per-token state from ContextVars so concurrent tasks each
        get independent stage handles.
        """
        tok = _CURRENT_TOKEN.get()
        if tok is None:
            raise RuntimeError("pipeline.stage() called outside a pipeline task")
        idx = _CURRENT_STAGE_IDX.get()
        _CURRENT_STAGE_IDX.set(idx + 1)
        return PipelineStage(self, idx, cycles, tok, self._timebase)

    # ------------------------------------------------------------------
    # Lock rt registry
    # ------------------------------------------------------------------

    def get_lock_rt(self, resource) -> Any:
        key = id(resource)
        if key not in self._lock_rts:
            self._lock_rts[key] = _make_lock_rt(resource.lock)
        return self._lock_rts[key]

    # ------------------------------------------------------------------
    # In-flight token search
    # ------------------------------------------------------------------

    def find(self, predicate: Callable) -> Optional[Any]:
        """Search in-flight snapshots; return first matching :class:`~..pipeline_ns._Snap`."""
        from ..pipeline_ns import _Snap
        for tok in reversed(self._in_flight):
            merged: dict = {}
            for snap in tok.stage_snapshots.values():
                merged.update(snap)
            s = _Snap(merged)
            if predicate(s):
                return s
        return None

    @property
    def trace(self) -> PipelineTrace:
        return self._trace


def _make_lock_rt(lock):
    """Instantiate the rt implementation for a given lock descriptor."""
    from .pipeline_locks_rt import QueueLockRt, BypassLockRt
    from ..pipeline_locks import QueueLock, BypassLock, RenameLock

    if isinstance(lock, BypassLock):
        return BypassLockRt(bypass_latency=lock.bypass_latency)
    # Default: QueueLock (also for RenameLock as a simplification for now)
    return QueueLockRt()
