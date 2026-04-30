"""Core solve helpers shared by api.py and solver back-ends.

These functions contain the implementation previously inlined in api.py.
Keeping them here breaks the potential circular import between api.py
(which imports the back-end registry) and python_backend.py (which needs
the solve logic).
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple

from zuspec.ir.core.data_type import DataTypeStruct, DataTypeClass
from .core.constraint_system import ConstraintSystem
from .frontend.constraint_system_builder import ConstraintSystemBuilder, BuildError
from .engine.search import BacktrackingSearch
from .engine.propagation import PropagationEngine
from .engine.seed_manager import SeedManager
from .engine.randomization import (
    RandomizedVariableOrdering,
    RandomizedValueOrdering,
    MRVWithRandomTiebreaking,
)

# ------------------------------------------------------------------ #
# Assignment result cache for bound-value objects                      #
# ------------------------------------------------------------------ #
# Maps (class, frozenset_of_bound_values) -> {field_name: value}
# for classes whose rand fields are fully determined by their bound
# (flow-input) fields. On a cache hit the solve step is skipped entirely.
_BOUND_ASSIGN_CACHE: Dict[Tuple[type, FrozenSet], Dict[str, int]] = {}

# Per-class cache of non-rand field names (for bound key extraction).
# Avoids iterating struct_type.fields on every call.
_BOUND_FIELD_NAMES: Dict[type, Tuple[str, ...]] = {}

# Per-class set of dotted field paths that are *actually referenced* by
# constraints as bound values.  Populated on the first solve for a class
# and used to build a minimal, stable cache key on all subsequent calls.
# Key: class type  Value: sorted tuple of dotted-path strings
_USED_BOUND_PATHS: Dict[type, Tuple[str, ...]] = {}

# Per-class snapshot of pool values used by constraints (for cache key).
# Key: class type  Value: dict of {field_name: tuple(values)}
# When pool slot values change (e.g. different register file contents), the
# cache key changes and the assignment is not reused.
_USED_POOL_VALUES: Dict[type, Dict[str, tuple]] = {}

# Set of class types known to have bound (non-rand composite) fields.
_BOUND_CLASSES: set = set()

# Set of class types known to NOT have bound fields.
_NONBOUND_CLASSES: set = set()

# Set of class types for which deterministic compilation has been attempted
# (prevents repeated analysis on classes that aren't fully determined).
_DETERMINISTIC_ANALYSIS_DONE: set = set()


def _get_bound_field_names(cls: type, struct_type) -> Tuple[str, ...]:
    """Return the non-rand top-level field names for *cls*, cached."""
    names = _BOUND_FIELD_NAMES.get(cls)
    if names is None:
        names = tuple(
            f.name for f in struct_type.fields
            if getattr(f, 'rand_kind', None) is None
        )
        _BOUND_FIELD_NAMES[cls] = names
    return names


def _getattr_dotted(obj: Any, dotted_path: str) -> Optional[int]:
    """Return the integer value at *dotted_path* relative to *obj*, or None."""
    parts = dotted_path.split('.')
    cur = obj
    for part in parts:
        cur = getattr(cur, part, None)
        if cur is None:
            return None
    if isinstance(cur, bool):
        return int(cur)
    if isinstance(cur, (int, float)):
        return int(cur)
    return None


def _make_bound_key_precise(obj: Any, cls: type) -> FrozenSet:
    """Return a cache key using only the constraint-relevant bound paths.

    Uses the per-class ``_USED_BOUND_PATHS`` table (populated on first solve)
    to extract only the field values that constraints actually reference.
    Also includes pool slot values from ``_USED_POOL_VALUES`` so that changes
    to resource pool contents (e.g. different register file state) produce a
    cache miss and trigger a fresh solve.
    """
    paths = _USED_BOUND_PATHS[cls]
    items = []
    for path in paths:
        val = _getattr_dotted(obj, path)
        if val is not None:
            items.append((path, val))
    # Include pool values in the key so that different pool contents don't
    # accidentally reuse a stale assignment.
    pool_values = _USED_POOL_VALUES.get(cls, {})
    for field_name, template_values in pool_values.items():
        # Read the current pool values from obj at solve time
        pool = _get_pool_for_field(obj, field_name)
        if pool is not None:
            resources = getattr(pool, 'resources', None) or getattr(pool, 'items', None)
            if resources:
                current = tuple(
                    int(getattr(r, 't', r)) if not isinstance(r, int) else r
                    for r in resources
                )
                items.append((f"_pool_{field_name}", current))
        else:
            # Fallback: use the template values recorded at first solve
            items.append((f"_pool_{field_name}", template_values))
    return frozenset(items)


def _get_pool_for_field(obj: Any, field_name: str):
    """Retrieve the pool object for a resource_ref field via __bind__."""
    try:
        from ..action_bind import parse_action_bind
        bind_map = parse_action_bind(obj)
        return bind_map.get(field_name) if bind_map else None
    except Exception:
        return None


def _ensure_output_payloads(obj: Any, struct_type) -> None:
    """Initialize any output buffer fields still holding the ``Output()`` marker.

    Called before applying a cached assignment so that dotted-path writes like
    ``out.t.kind = 5`` have a real dataclass object to write into.
    """
    try:
        from zuspec.ir.core.fields import FieldInOut
        from zuspec.dataclasses.solver.frontend.constraint_system_builder import (
            _OutputBufferProxy,
        )
    except ImportError:
        return

    import dataclasses as _dc
    import typing as _typing

    for field in struct_type.fields:
        if not (isinstance(field, FieldInOut) and field.is_out):
            continue
        payload = getattr(obj, field.name, None)

        # Unwrap existing proxy.
        if isinstance(payload, _OutputBufferProxy):
            payload = payload.t

        if payload is not None and _dc.is_dataclass(payload):
            setattr(obj, field.name, _OutputBufferProxy(payload))
            continue

        # Look up the payload type from the Python class annotation.
        obj_cls = type(obj)
        if not _dc.is_dataclass(obj_cls):
            continue
        for dc_field in _dc.fields(obj_cls):
            if dc_field.name != field.name:
                continue
            args = _typing.get_args(dc_field.type)
            if args and isinstance(args[0], type) and _dc.is_dataclass(args[0]):
                setattr(obj, field.name, _OutputBufferProxy(args[0]()))
            break


def _apply_cached_assignment(obj: Any, cached: Dict[str, int]) -> None:
    """Apply a cached scalar-field assignment directly to *obj*.

    Handles dotted paths (e.g. ``"out.t.kind"``) by walking the attribute
    chain — the same logic as the inner loop in ``_apply_solution``.
    Resource-id paths (e.g. ``"rs1.id"``) are routed to
    ``_store_resource_hint`` when the intermediate field is not yet acquired.
    """
    for var_name, value in cached.items():
        if "." in var_name:
            parts = var_name.split(".")
            target = obj
            stored = False
            for part in parts[:-1]:
                next_val = getattr(target, part, None)
                if next_val is None and target is obj and len(parts) == 2:
                    if _is_resource_ref_field(obj, part):
                        attr_suffix = parts[-1]
                        if attr_suffix == 't':
                            # Write-target for lock() resource.
                            # var_name is already "field.t"; that is the hint key.
                            _store_resource_hint(obj, var_name, value)
                        else:
                            _store_resource_hint(obj, part, value)
                        stored = True
                    break
                target = next_val
            if not stored and target is not None:
                setattr(target, parts[-1], value)
        else:
            setattr(obj, var_name, value)


class RandomizationError(Exception):
    """Raised when randomization fails (UNSAT, timeout, or build error)."""


class RandomizationResult:
    """Outcome of a single randomization attempt."""

    def __init__(
        self,
        success: bool,
        assignment: Optional[Dict[str, int]] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.assignment = assignment or {}
        self.error = error

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:
        if self.success:
            return f"RandomizationResult(success=True, {len(self.assignment)} vars)"
        return f"RandomizationResult(success=False, error={self.error!r})"


# ------------------------------------------------------------------ #
# Shared helpers                                                       #
# ------------------------------------------------------------------ #

def _extract_struct_type(obj: Any) -> DataTypeStruct:
    """Return the IR DataTypeStruct attached to *obj* or its class.

    Raises ``RandomizationError`` when the struct cannot be found.
    """
    if hasattr(obj, "_zdc_struct"):
        return obj._zdc_struct

    cls = obj.__class__
    if hasattr(cls, "_zdc_struct"):
        return cls._zdc_struct

    from ..types import Component  # noqa: PLC0415
    if isinstance(obj, Component):
        if hasattr(obj, "_zdc_struct"):
            return obj._zdc_struct
        if hasattr(cls, "_zdc_struct"):
            return cls._zdc_struct

    # Last resort: build on demand via DataModelFactory
    try:
        from ..data_model_factory import DataModelFactory
        factory = DataModelFactory()
        ctx = factory.build([cls])
        type_name = f"{cls.__module__}.{cls.__qualname__}"
        struct = ctx.type_m.get(type_name) or ctx.type_m.get(cls.__qualname__)
        if struct:
            cls._zdc_struct = struct
            return struct
    except Exception as exc:
        raise RandomizationError(
            f"Cannot extract IR struct type from {cls.__name__}: {exc}"
        ) from exc

    raise RandomizationError(
        f"Cannot extract IR struct type from {cls.__name__}. "
        "Ensure the class is decorated with @dataclass from zuspec.dataclasses"
    )


def _solve_constraint_system(
    system: ConstraintSystem,
    seed: Optional[int],
    timeout_ms: Optional[int],
) -> RandomizationResult:
    """Solve *system* and return a ``RandomizationResult``."""
    try:
        from .frontend.constraint_compiler import ConstraintCompiler, CompilationError

        seed_manager = SeedManager(global_seed=seed)
        propagation_engine = PropagationEngine()

        compiler = ConstraintCompiler(system.variables)
        for constraint in system.constraints:
            try:
                propagators = compiler.compile(constraint)
                for prop in propagators:
                    propagation_engine.add_propagator(prop)
            except CompilationError as exc:
                warnings.warn(f"Failed to compile constraint: {exc}")

        propagation_engine.set_variables(compiler.variables)

        # MRV (smallest-domain-first) with random tiebreaking reduces
        # backtracking significantly vs pure random variable ordering.
        var_heuristic = MRVWithRandomTiebreaking(
            seed_manager=seed_manager, context="var_order")
        val_heuristic = RandomizedValueOrdering(
            seed_manager=seed_manager, context="val_order"
        )

        search = BacktrackingSearch(
            propagation_engine,
            var_heuristic=var_heuristic,
            val_heuristic=val_heuristic,
        )

        solution = search.solve(system.variables)
        if solution is not None:
            return RandomizationResult(success=True, assignment=solution)
        return RandomizationResult(success=False, error="No solution found (UNSAT)")

    except Exception as exc:
        return RandomizationResult(success=False, error=f"Solver error: {exc}")


def _store_resource_hint(obj: Any, field_name: str, value: int) -> None:
    """Store a solved resource pool-slot id in ``obj._zdc_resource_hints``."""
    hints = getattr(obj, '_zdc_resource_hints', None)
    if hints is None:
        hints = {}
        try:
            object.__setattr__(obj, '_zdc_resource_hints', hints)
        except (AttributeError, TypeError):
            obj._zdc_resource_hints = hints
    hints[field_name] = value


def _is_resource_ref_field(obj: Any, field_name: str) -> bool:
    """Return True if *field_name* is a ``resource_ref`` dataclass field on *obj*."""
    import dataclasses as _dc2
    try:
        for f in _dc2.fields(obj):
            if f.name == field_name and f.metadata.get('kind') == 'resource_ref':
                return True
    except TypeError:
        pass
    return False


def _apply_solution(
    obj: Any,
    assignment: Dict[str, int],
    system: ConstraintSystem,
) -> None:
    """Write *assignment* values back into *obj*'s fields."""
    # First pass: scalar fields
    for var_name, value in assignment.items():
        if "[" in var_name:
            continue
        if "." in var_name:
            parts = var_name.split(".")
            target = obj
            stored = False
            for part in parts[:-1]:
                next_val = getattr(target, part, None)
                if next_val is None and target is obj and len(parts) == 2:
                    if _is_resource_ref_field(obj, part):
                        attr_suffix = parts[-1]
                        if attr_suffix == 't':
                            # Write-target for lock() resource: only store the hint
                            # if at least one constraint actually referenced this
                            # write-target (write-enable-via-absence semantics).
                            if var_name in system.referenced_lock_writes:
                                _store_resource_hint(obj, var_name, value)
                        else:
                            _store_resource_hint(obj, part, value)
                        stored = True
                    break
                target = next_val
            if not stored and target is not None:
                setattr(target, parts[-1], value)
        else:
            if hasattr(obj, var_name):
                setattr(obj, var_name, value)

    # Second pass: array fields
    for field_name, metadata in system.array_metadata.items():
        element_names = metadata["element_names"]
        size = metadata["size"]
        is_variable_size = metadata.get("is_variable_size", False)
        length_var_name = metadata.get("length_var_name", None)

        actual_length = size
        if is_variable_size and length_var_name:
            actual_length = assignment.get(length_var_name, 0)

        array_values = []
        for i in range(actual_length):
            elem_name = element_names[i]
            if elem_name in assignment:
                array_values.append(assignment[elem_name])
            else:
                raise RandomizationError(
                    f"Missing solution for array element {elem_name}"
                )

        if hasattr(obj, field_name):
            setattr(obj, field_name, array_values)
        elif "." in field_name:
            parts = field_name.split(".")
            target = obj
            for part in parts[:-1]:
                target = getattr(target, part)
            setattr(target, parts[-1], array_values)


def _try_compile_deterministic(cls: type, struct_type) -> Optional[object]:
    """Attempt to compile a deterministic solver function for *cls*.

    Returns a compiled callable suitable for ``cls._zdc_compiled_solve``,
    or ``None`` if the class is not fully determined by its inputs.
    """
    # resource_ref fields (zdc.lock/share) have id variables that need special
    # write-back to _zdc_resource_hints.  Skip deterministic compilation for
    # such actions until that path is fully implemented.
    import dataclasses as _dc2
    if hasattr(cls, '__dataclass_fields__'):
        try:
            if any(f.metadata.get('kind') == 'resource_ref' for f in _dc2.fields(cls)):
                return None
        except TypeError:
            pass

    try:
        from .deterministic.variable_status import build_from_struct
        from .deterministic.constraint_analyser import ConstraintAnalyser
        from .deterministic.python_emitter import PythonFunctionEmitter

        var_map = build_from_struct(struct_type, py_class=cls)
        analyser = ConstraintAnalyser()
        plan = analyser.analyse(cls, struct_type, var_map)

        if plan.underdetermined:
            return None  # Not fully determined — cannot use deterministic path

        emitter = PythonFunctionEmitter()
        return emitter.emit(plan)
    except Exception:
        return None  # Any failure → fall back to solver


def _struct_rand_field_names(struct_type) -> frozenset:
    """Return the names of rand fields in *struct_type*."""
    return frozenset(
        f.name for f in struct_type.fields
        if getattr(f, 'rand_kind', None) is not None
    )


def randomize_bound_cached(
    obj: Any,
    struct_type,
    seed: Optional[int],
    timeout_ms: Optional[int],
) -> None:
    """Randomize *obj* using a result cache keyed on its bound field values.

    For classes whose rand fields are fully determined by their bound
    (flow-input) fields (e.g. Decode given *fetch.instr*), the full
    build+compile+solve pipeline is only executed once per unique
    combination of bound values.  Subsequent calls with the same bound
    values return the cached assignment immediately, costing only a dict
    lookup plus a few ``setattr`` calls (~1-2 µs).

    Falls back to a fresh solve when:
    - the assignment is not yet cached (first call for this bound-key), or
    - the solve produces more than one valid assignment (non-deterministic).

    The result is stored as the subset of the assignment that maps to
    actual struct fields (temp/bool/const compiler variables are filtered
    out), so the cached dict is small and ``_apply_cached_assignment`` can
    apply it cheaply.
    """
    cls = type(obj)

    # Deterministic fast path: if a pre-compiled solve function exists, use it.
    compiled_solve = getattr(cls, '_zdc_compiled_solve', None)
    if compiled_solve is not None:
        _ensure_output_payloads(obj, struct_type)
        compiled_solve(obj)
        return

    # First time for this class: attempt to compile a deterministic solver.
    if cls not in _DETERMINISTIC_ANALYSIS_DONE:
        _DETERMINISTIC_ANALYSIS_DONE.add(cls)
        fn = _try_compile_deterministic(cls, struct_type)
        if fn is not None:
            cls._zdc_compiled_solve = fn
            _ensure_output_payloads(obj, struct_type)
            fn(obj)
            return

    # Fast path: used-bound-paths already known — build a minimal precise key.
    if cls in _USED_BOUND_PATHS:
        used = _USED_BOUND_PATHS[cls]
        if used:
            # Has bound paths — results are deterministic given those paths, use cache.
            bound_key = _make_bound_key_precise(obj, cls)
            cache_key = (cls, bound_key)
            cached = _BOUND_ASSIGN_CACHE.get(cache_key)
            if cached is not None:
                _ensure_output_payloads(obj, struct_type)
                _apply_cached_assignment(obj, cached)
                return
        else:
            # No bound paths — results are seed-dependent; skip cache entirely.
            cache_key = None
    else:
        # First call for this class: no used-paths known yet; key is unused.
        cache_key = None

    # Cache miss: build constraint system, solve, cache result.
    builder = ConstraintSystemBuilder()
    try:
        system = builder.build_from_struct(struct_type, obj=obj)
    except BuildError as exc:
        raise RandomizationError(f"Failed to build constraint system: {exc}") from exc

    # Record which bound paths were actually used; build the precise key now.
    if cls not in _USED_BOUND_PATHS:
        used = tuple(sorted(builder.expr_parser.used_bound_paths))
        _USED_BOUND_PATHS[cls] = used
        # Record pool values used by constraints so future cache lookups can
        # include them in the key and detect when pool contents change.
        pool_vals = dict(builder.expr_parser.used_pool_values)
        if pool_vals:
            _USED_POOL_VALUES[cls] = pool_vals
        bound_key = _make_bound_key_precise(obj, cls)
        cache_key = (cls, bound_key)

    result = _solve_constraint_system(system, seed, timeout_ms)
    if not result.success:
        raise RandomizationError(f"No solution found: {result.error}")

    _apply_solution(obj, result.assignment, system)

    # Only cache if the class has bound paths that constrain rand fields.
    # With no bound paths the solve is seed-dependent randomization — caching
    # would freeze the result and prevent different seeds from producing
    # different values.
    if not _USED_BOUND_PATHS.get(cls):
        return

    # Cache only the variables the solver actually produced (filter compiler
    # temporaries, array element vars, and unreferenced lock write targets).
    # Lock write vars (of the form "field.t") are only cached when they were
    # actually referenced in a constraint; otherwise the resource should retain
    # its current pool value (write-enable-via-absence-of-constraint semantics).
    solver_var_names = frozenset(system.variables.keys())
    ref_lock_writes = system.referenced_lock_writes
    _BOUND_ASSIGN_CACHE[cache_key] = {
        k: v for k, v in result.assignment.items()
        if k in solver_var_names and "[" not in k
        and not (k.endswith(".t")
                 and f"{k[:-2]}.id" in solver_var_names
                 and k not in ref_lock_writes)
    }


