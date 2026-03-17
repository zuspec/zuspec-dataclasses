"""Python solver back-end.

Wraps the existing ConstraintSystemBuilder + BacktrackingSearch engine.
All implementation lives in ``_core_solve``; this class is a thin adapter
that satisfies the ``SolverBackend`` protocol.
"""
from __future__ import annotations

import weakref
from typing import Any, Optional, Tuple


# Per-class cache: avoids rebuilding the struct type and constraint system
# on every randomize() call.  Keyed by class id; uses weakref so the cache
# entry disappears when the class is collected.
_class_cache: dict[int, Tuple[Any, Any]] = {}


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
            cls = obj.__class__
            cache_key = id(cls)
            cached = _class_cache.get(cache_key)
            if cached is not None:
                struct_type, template_system = cached
            else:
                struct_type = _extract_struct_type(obj)
                builder = ConstraintSystemBuilder()
                template_system = builder.build_from_struct(struct_type)
                _class_cache[cache_key] = (struct_type, template_system)

            # Deep-copy the constraint system so each solve gets fresh domains
            constraint_system = template_system.copy()

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
