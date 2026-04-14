"""Async pipeline DSL namespace for ``zuspec.dataclasses``.

This module provides the ``pipeline`` singleton (exposed as ``zdc.pipeline``)
which is the entry point for the async pipeline behavioral model.

Minimal 3-stage example::

    @zdc.dataclass
    class Adder(zdc.Component):
        clock: zdc.bit = zdc.input()

        @zdc.pipeline(clock=lambda s: s.clock)
        async def run(self):
            async with zdc.pipeline.stage() as FETCH:
                a = self.a_in
                b = self.b_in

            async with zdc.pipeline.stage() as COMPUTE:
                result = a + b

            async with zdc.pipeline.stage() as WRITEBACK:
                self.sum_out = result

Pipeline resource hazard protocol::

    zdc.pipeline.reserve(self.rf[rd])       # claim write slot
    val = await zdc.pipeline.block(self.rf[rs1])  # wait for RAW
    zdc.pipeline.write(self.rf[rd], val)    # bypass forward
    zdc.pipeline.release(self.rf[rd])       # relinquish claim

Observer / trace API::

    comp.run_trace.add_observer(lambda tok, ev, **kw: print(tok.token_id, ev))
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .pipeline_resource import PipelineResource, _ResourceProxy

# ContextVar that holds the active PipelineRuntime during execution.
# When None, the stub implementations are in effect (importable but no-op).
_PIPELINE_RT: ContextVar = ContextVar('_PIPELINE_RT', default=None)

# Per-token ContextVars — each spawned token task gets its own copy.
_CURRENT_TOKEN: ContextVar = ContextVar('_CURRENT_TOKEN', default=None)
_CURRENT_STAGE_IDX: ContextVar = ContextVar('_CURRENT_STAGE_IDX', default=0)
_CURRENT_STAGE: ContextVar = ContextVar('_CURRENT_STAGE', default=None)


class _Snap:
    """Attribute-access view of a frozen token local-variable snapshot.

    Missing attribute names return ``None`` rather than raising
    ``AttributeError``, making ``find()`` predicates easy to write.
    """

    def __init__(self, data: dict):
        object.__setattr__(self, '_data', data)

    def __getattr__(self, name: str):
        return object.__getattribute__(self, '_data').get(name)

    def __repr__(self) -> str:  # pragma: no cover
        return f"_Snap({object.__getattribute__(self, '_data')!r})"


class _StageHandle:
    """Async context manager returned by ``zdc.pipeline.stage()``.

    At import / stub time this is the real object used.  During ``rt``
    execution ``_PipelineNamespace.stage()`` returns a ``PipelineStage``
    instead (which has the same async CM interface plus cycle accounting).
    """

    def __init__(self, *, cycles: int = 1):
        self._cycles = cycles

    async def __aenter__(self) -> "_StageHandle":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def stall(self, n: int = 1) -> None:
        """Extend this stage's occupancy by *n* additional cycles (stub)."""

    async def bubble(self) -> None:
        """Invalidate this token; slot drains without side effects (stub)."""

    @property
    def cycle(self) -> int:
        """Current cycle number (0-based) within this stage invocation."""
        return 0

    @property
    def valid(self) -> bool:
        """False if ``bubble()`` has been called."""
        return True


async def _auto_stall_wrap(rt, coro):
    """Await *coro*; if simulated time advanced, charge stall cycles to current stage.

    Used by ``block()`` and ``reserve()`` so any suspension is automatically
    reflected as extra stall cycles on the active :class:`PipelineStage`.
    """
    tb = rt._timebase
    stage = _CURRENT_STAGE.get()
    tok = _CURRENT_TOKEN.get()
    t_before = tb._current_time
    result = await coro
    elapsed_fs = tb._current_time - t_before
    if elapsed_fs > 0 and stage is not None and tok is not None:
        period = getattr(rt._domain, 'period', None)
        if period is not None:
            from .rt.timebase import Timebase
            period_fs = Timebase._time_to_fs(period)
            if period_fs > 0:
                extra = elapsed_fs // period_fs
                if extra > 0:
                    stage._extra += extra
                    tok.cycle += extra
                    rt._slots.extend_slot(
                        stage._stage_idx, stage._enter, stage._cycles, stage._extra
                    )
    return result


class _PipelineNamespace:
    """Singleton exposed as ``zdc.pipeline``.

    Acts as a decorator (via ``__call__``), a stage context-manager source,
    and a namespace for hazard operations.

    Decorator usage::

        @zdc.pipeline(clock=lambda s: s.clk, reset=lambda s: s.rst_n)
        async def run(self): ...

    Stage context manager::

        async with zdc.pipeline.stage() as ST:
            ...

    Hazard operations (call-through to lock rt when executing)::

        zdc.pipeline.reserve(self.rf[rd])
        val = await zdc.pipeline.block(self.rf[rs1])
        zdc.pipeline.write(self.rf[rd], val)
        zdc.pipeline.release(self.rf[rd])
    """

    # ------------------------------------------------------------------
    # Decorator use
    # ------------------------------------------------------------------

    def __call__(
        self,
        func=None,
        *,
        clock=None,   # lambda s: s.clk_domain — ClockDomain
        reset=None,   # lambda s: s.rst_domain — ResetDomain
    ):
        """Decorate an async pipeline method.

        Supports both ``@zdc.pipeline`` (bare) and
        ``@zdc.pipeline(clock=..., reset=...)`` (parametric) forms.

        Args:
            func:   The async method being decorated (bare form).
            clock:  Lambda ``lambda self: self.clk`` returning a
                    ``ClockDomain`` instance.
            reset:  Lambda ``lambda self: self.rst_n`` returning a
                    ``ResetDomain`` instance (optional).
        """
        def decorator(method):
            method._zdc_async_pipeline = True
            method._zdc_pipeline_clock = clock
            method._zdc_pipeline_reset = reset
            return method

        if func is not None:
            return decorator(func)
        return decorator

    # ------------------------------------------------------------------
    # Stage context manager
    # ------------------------------------------------------------------

    def stage(self, *, cycles: int = 1):
        """Return an async context manager for one pipeline stage boundary.

        During ``rt`` execution this returns a ``PipelineStage`` with full
        cycle accounting.  Outside of ``rt`` execution it returns a stub
        ``_StageHandle`` that is a no-op.

        Args:
            cycles: Number of clock cycles this stage occupies (default 1).
        """
        rt = _PIPELINE_RT.get()
        if rt is not None:
            return rt.stage_handle(cycles)
        return _StageHandle(cycles=cycles)

    # ------------------------------------------------------------------
    # Pipeline resource factory
    # ------------------------------------------------------------------

    def resource(self, size: int, *, lock=None) -> "PipelineResource":
        """Declare a pipeline-tracked resource with address space *size*.

        Args:
            size: Number of distinct addresses (e.g. 32 for a register file).
            lock: A :class:`HazardLock` instance controlling hazard strategy.
                  Defaults to :class:`QueueLock`.
        """
        from .pipeline_resource import PipelineResource
        return PipelineResource(size=size, lock=lock)

    # ------------------------------------------------------------------
    # Hazard operations
    # ------------------------------------------------------------------

    async def reserve(self, proxy, mode: str = "write") -> None:
        """Claim the address of *proxy*; may stall if the resource is full.

        Must be called with ``await`` — e.g. ``await zdc.pipeline.reserve(rf[rd])``.
        Stalling can occur when the backing lock has finite capacity (e.g. a
        :class:`RenameLock` with a full rename buffer).  Any suspension is
        automatically charged as extra stall cycles to the current stage.

        Args:
            proxy: A ``_ResourceProxy`` (i.e. ``self.rf[addr]``).
            mode:  ``"write"`` (default) or ``"read"``.
        """
        rt = _PIPELINE_RT.get()
        if rt is not None:
            lock_rt = rt.get_lock_rt(proxy.resource)
            await _auto_stall_wrap(rt, lock_rt.reserve(proxy.addr, mode))

    async def block(self, proxy):
        """Await until *proxy* address is safe to read (all pending writers drained).

        Any cycles spent waiting are automatically charged as stall cycles to
        the current stage (auto-stall).

        Args:
            proxy: A ``_ResourceProxy`` (i.e. ``self.rf[addr]``).

        Returns:
            The forwarded value if the lock supports bypass, else ``None``.
        """
        rt = _PIPELINE_RT.get()
        if rt is not None:
            lock_rt = rt.get_lock_rt(proxy.resource)
            return await _auto_stall_wrap(rt, lock_rt.block(proxy.addr))

    def write(self, proxy, value) -> None:
        """Deposit *value* to the bypass network for *proxy* address.

        Args:
            proxy: A ``_ResourceProxy`` (i.e. ``self.rf[addr]``).
            value: The value to forward to pending readers.
        """
        rt = _PIPELINE_RT.get()
        if rt is not None:
            lock_rt = rt.get_lock_rt(proxy.resource)
            lock_rt.write(proxy.addr, value)

    def release(self, proxy) -> None:
        """Relinquish the write claim on *proxy* address.

        Args:
            proxy: A ``_ResourceProxy`` (i.e. ``self.rf[addr]``).
        """
        rt = _PIPELINE_RT.get()
        if rt is not None:
            lock_rt = rt.get_lock_rt(proxy.resource)
            lock_rt.release(proxy.addr)

    async def acquire(self, proxy, mode: str = "write") -> None:
        """Combined ``reserve`` + ``block`` — await and claim *proxy* address.

        Args:
            proxy: A ``_ResourceProxy`` (i.e. ``self.rf[addr]``).
            mode:  ``"write"`` (default) or ``"read"``.
        """
        await self.reserve(proxy, mode)
        await self.block(proxy)

    def snapshot(self, **kwargs) -> None:
        """Store key-value data into the current stage's snapshot dict.

        The stored values become searchable via :meth:`find`.  Call inside a
        stage body to annotate the in-flight token with pipeline-visible state.

        Example::

            async with zdc.pipeline.stage() as IF:
                zdc.pipeline.snapshot(pc=self.pc, opcode=instr & 0x7F)
        """
        tok = _CURRENT_TOKEN.get()
        stage = _CURRENT_STAGE.get()
        if tok is None or stage is None:
            return
        stage_idx = stage._stage_idx
        existing = tok.stage_snapshots.get(stage_idx)
        if existing is None:
            tok.stage_snapshots[stage_idx] = dict(kwargs)
        else:
            existing.update(kwargs)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def find(self, predicate: Callable) -> "_Snap | None":
        """Search in-flight token snapshots; return the first match or ``None``.

        Args:
            predicate: Callable ``(snap: _Snap) -> bool`` tested against
                       each in-flight token's merged variable snapshot,
                       from newest to oldest.
        """
        rt = _PIPELINE_RT.get()
        if rt is not None:
            return rt.find(predicate)
        return None

    def current_cycle(self) -> int:
        """Return the current pipeline cycle for this token.

        Inside a pipeline stage, returns the cycle at which the current token
        entered that stage.  Outside of ``rt`` execution returns 0.
        """
        tok = _CURRENT_TOKEN.get()
        if tok is not None:
            return tok.cycle
        rt = _PIPELINE_RT.get()
        if rt is not None:
            return rt._cycle
        return 0


#: Public singleton — ``import zuspec.dataclasses as zdc; zdc.pipeline``
pipeline = _PipelineNamespace()
