"""Python solver back-end.

Wraps the existing ConstraintSystemBuilder + BacktrackingSearch engine.
All implementation lives in ``_core_solve``; this class is a thin adapter
that satisfies the ``SolverBackend`` protocol.
"""
from __future__ import annotations

import weakref
from typing import Any, Optional, Tuple


# Per-class cache: avoids rebuilding the struct type and constraint system
# on every randomize() call.  WeakKeyDictionary keyed by the class object
# itself so entries are evicted automatically when the class is GC'd.
_class_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

# Per-(class, comp-snapshot) cache: when a class has a bound comp, cache by
# a frozen snapshot of the comp's relevant field values.  This avoids
# rebuilding the constraint system across iterations where comp is deterministic.
_comp_cache: dict = {}  # (cls, comp_key) -> (struct_type, template_system)


def _comp_snapshot_key(comp) -> Optional[tuple]:
    """Return a hashable key from comp's non-private scalar and list-of-primitive fields.

    Only includes fields whose values are stable primitives or lists thereof.
    Lists of component objects or other complex types are skipped to avoid
    unhashable or identity-dependent cache keys.
    """
    _PRIM = (int, float, bool, str, type(None))
    try:
        parts = []
        for k, v in sorted(vars(comp).items()):
            if k.startswith('_'):
                continue
            if isinstance(v, _PRIM):
                parts.append((k, v))
            elif isinstance(v, list) and all(isinstance(x, _PRIM) for x in v):
                parts.append((k, tuple(v)))
        # Require at least one field to distinguish instances; return None
        # if there is nothing stable to key on (e.g. pss_top whose fields
        # are all child component objects).
        if not parts:
            return None
        return (type(comp), tuple(parts))
    except Exception:
        return None


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
            # Check the comp-snapshot cache first (handles cases where comp
            # fields are the same across iterations, e.g. pad-assignment).
            comp = getattr(obj, 'comp', None)
            comp_key = _comp_snapshot_key(comp) if comp is not None else None
            if comp_key is not None:
                cached_comp = _comp_cache.get((cls, comp_key))
                if cached_comp is not None:
                    struct_type, template_system, cached_assignment = cached_comp
                    # Fast path: if all vars were singletons on first solve, reuse result.
                    if cached_assignment is not None:
                        _apply_solution(obj, cached_assignment, template_system)
                        return
                else:
                    struct_type = _extract_struct_type(obj)
                    builder = ConstraintSystemBuilder()
                    template_system = builder.build_from_struct(struct_type, obj=obj)
                    _comp_cache[(cls, comp_key)] = (struct_type, template_system, None)
            else:
                cached = _class_cache.get(cls)
                if cached is not None:
                    struct_type, template_system = cached
                    if _has_bound_object_fields(obj, struct_type):
                        builder = ConstraintSystemBuilder()
                        template_system = builder.build_from_struct(struct_type, obj=obj)
                else:
                    struct_type = _extract_struct_type(obj)
                    builder = ConstraintSystemBuilder()
                    if _has_bound_object_fields(obj, struct_type):
                        template_system = builder.build_from_struct(struct_type, obj=obj)
                    else:
                        template_system = builder.build_from_struct(struct_type)
                        _class_cache[cls] = (struct_type, template_system)

            # Deep-copy the constraint system so each solve gets fresh domains
            constraint_system = template_system.copy()

            result = _solve_constraint_system(constraint_system, seed, timeout_ms)
            if result.success:
                _apply_solution(obj, result.assignment, constraint_system)
                # If this was a comp-keyed entry and the solution came from the
                # singleton fast-path (all vars determined), cache the assignment
                # for future calls to bypass the solver entirely.
                if comp_key is not None and _is_singleton_solution(result, constraint_system):
                    struct_type_c, tmpl_c, old_asgn = _comp_cache.get((cls, comp_key), (None, None, None))
                    if old_asgn is None and tmpl_c is not None:
                        _comp_cache[(cls, comp_key)] = (struct_type_c, tmpl_c, dict(result.assignment))
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


def _is_singleton_solution(result, constraint_system) -> bool:
    """True if every decision variable was a singleton after propagation.

    When this is the case the solution is seed-independent and can be reused
    across iterations without re-running the solver.
    """
    if not result.success:
        return False
    try:
        for vname, v in constraint_system.variables.items():
            if v.domain.size() != 1:
                return False
        return True
    except Exception:
        return False


def _has_bound_object_fields(obj: Any, struct_type) -> bool:
    """Return True if *obj* has non-rand fields that are composite objects.

    When such fields exist, constraints can reference their sub-attributes
    (e.g. ``self.next_.domain_A`` or ``self.comp.some_list``), so the
    constraint system must be rebuilt per-instance rather than cached.
    """
    try:
        rand_names: set = set()
        for field in struct_type.fields:
            if getattr(field, 'rand_kind', None) is not None:
                rand_names.add(field.name)
        for field in struct_type.fields:
            if field.name in rand_names:
                continue
            val = getattr(obj, field.name, None)
            if val is not None and not isinstance(val, (int, float, bool, str)):
                return True
        # The 'comp' field is not in struct_type.fields but constraints can
        # reference comp attributes (e.g. x in comp.valid_pads).
        comp = getattr(obj, 'comp', None)
        if comp is not None:
            return True
    except Exception:
        pass
    return False
