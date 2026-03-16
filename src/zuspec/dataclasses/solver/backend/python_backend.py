"""Python solver back-end.

Wraps the existing ConstraintSystemBuilder + BacktrackingSearch engine.
All implementation lives in ``_core_solve``; this class is a thin adapter
that satisfies the ``SolverBackend`` protocol.
"""
from __future__ import annotations

from typing import Any, Optional


class PythonSolverBackend:
    """Back-end that drives the pure-Python CP engine."""

    @property
    def name(self) -> str:
        return "python"

    @property
    def available(self) -> bool:
        return True  # always present — no native library required

    def randomize(
        self,
        obj: Any,
        seed: Optional[int] = None,
        timeout_ms: Optional[int] = 1000,
    ) -> None:
        from .._core_solve import (
            _extract_struct_type,
            _solve_constraint_system,
            _apply_solution,
            RandomizationError,
        )
        from ..frontend.constraint_system_builder import (
            ConstraintSystemBuilder,
            BuildError,
        )

        try:
            struct_type = _extract_struct_type(obj)
            builder = ConstraintSystemBuilder()
            constraint_system = builder.build_from_struct(struct_type)
            result = _solve_constraint_system(constraint_system, seed, timeout_ms)
            if result.success:
                _apply_solution(obj, result.assignment, constraint_system)
            else:
                msg = result.error or "constraints unsatisfiable"
                raise RandomizationError(f"No solution found: {msg}")
        except RandomizationError:
            raise
        except BuildError as exc:
            raise RandomizationError(
                f"Failed to build constraint system: {exc}"
            ) from exc
        except Exception as exc:
            raise RandomizationError(f"Randomization failed: {exc}") from exc

    def randomize_with(
        self,
        obj: Any,
        with_block: Any,
        seed: Optional[int] = None,
        timeout_ms: Optional[int] = 1000,
    ) -> None:
        # Phase 1: randomize_with goes through the context manager in api.py,
        # not through this method.  Full wiring deferred to Phase 9.
        raise NotImplementedError(
            "randomize_with on PythonSolverBackend is not yet wired; "
            "use the randomize_with() context manager from zuspec.dataclasses"
        )
