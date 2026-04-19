"""``zdc.stage`` — method decorator for the old sync @zdc.stage pipeline API.

The ``stage`` singleton exported from ``zuspec.dataclasses`` supports three
usage patterns:

1. Bare decorator::

       @zdc.stage
       def S1(self) -> (zdc.u32,): ...

2. Parametric decorator::

       @zdc.stage(no_forward=True)
       def MEM(self, addr: zdc.u32) -> (zdc.u32,): ...

3. Static helper calls (inside stage/sync method bodies or pipeline body)::

       zdc.stage.stall(self, ~self.valid_in)
       zdc.stage.flush(self.IF, self.branch_taken)
       zdc.stage.cancel(self, self.mispredict)
       zdc.stage.ready(self.IF)          # inside @zdc.sync

4. Multi-cycle context manager (inside ``@zdc.pipeline`` body)::

       with zdc.stage.cycles(2):
           (result,) = self.EX(insn)

These helpers are **no-ops at runtime** — they are parsed statically by
:func:`~zuspec.dataclasses.data_model_factory.DataModelFactory._build_pipeline_irs`
to build :class:`~zuspec.ir.core.pipeline.StageMethodIR` objects.
"""
from __future__ import annotations

from contextlib import contextmanager


class _CyclesCM:
    """No-op context manager returned by ``zdc.stage.cycles(N)``."""
    def __init__(self, n: int) -> None:
        self._n = n

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _StageDecorator:
    """Callable object exposed as ``zdc.stage``."""

    # ------------------------------------------------------------------
    # Decorator usage
    # ------------------------------------------------------------------

    def __call__(self, func=None, *, no_forward: bool = False, cycles: int = 1):
        """Decorate a method as a pipeline stage.

        Supports both bare (``@zdc.stage``) and parametric
        (``@zdc.stage(no_forward=True)``) forms.

        Args:
            func:       The method being decorated (bare form only).
            no_forward: When ``True``, the stage does not participate in
                        forwarding — any RAW hazard it produces must be
                        resolved by stalling.  Default ``False``.
            cycles:     Number of clock cycles this stage occupies.
                        Default 1.
        """
        def decorator(f):
            f._zdc_stage = True
            f._zdc_no_forward = no_forward
            f._zdc_cycles = cycles
            return f

        if func is not None:
            # Bare @zdc.stage — func is the decorated method
            return decorator(func)
        return decorator

    # ------------------------------------------------------------------
    # Multi-cycle context manager
    # ------------------------------------------------------------------

    def cycles(self, n: int) -> _CyclesCM:
        """Context manager that marks the enclosed stage call(s) as *n*-cycle.

        At runtime this is a no-op; the AST of the enclosing
        ``@zdc.pipeline`` method body is parsed statically by
        :class:`~zuspec.dataclasses.data_model_factory.DataModelFactory`
        to extract the cycle count.

        Usage inside a ``@zdc.pipeline`` body::

            with zdc.stage.cycles(2):
                (result,) = self.EX(insn)

        Args:
            n: Number of clock cycles.
        """
        return _CyclesCM(n)

    # ------------------------------------------------------------------
    # Runtime-stub helpers (no-ops; parsed statically by DataModelFactory)
    # ------------------------------------------------------------------

    @staticmethod
    def stall(stage_or_self, cond=None) -> None:
        """Declare that this stage stalls when *cond* is True. No-op at runtime."""

    @staticmethod
    def flush(stage_or_self, cond=None) -> None:
        """Declare a flush of *stage_or_self* when *cond* is True. No-op at runtime."""

    @staticmethod
    def cancel(stage_or_self, cond=None) -> None:
        """Declare that this stage cancels when *cond* is True. No-op at runtime."""

    @staticmethod
    def ready(stage_ref) -> bool:
        """Return whether *stage_ref* is ready (True at runtime — stub). No-op at synthesis."""
        return True


#: Singleton exposed as ``zdc.stage``.
stage = _StageDecorator()
