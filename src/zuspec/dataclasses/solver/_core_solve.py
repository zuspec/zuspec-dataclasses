"""Core solve helpers shared by api.py and solver back-ends.

These functions contain the implementation previously inlined in api.py.
Keeping them here breaks the potential circular import between api.py
(which imports the back-end registry) and python_backend.py (which needs
the solve logic).
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, Optional

from ..ir.data_type import DataTypeStruct, DataTypeClass
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
            for part in parts[:-1]:
                target = getattr(target, part)
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
