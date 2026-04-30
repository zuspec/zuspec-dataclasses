"""Variable status tracking for deterministic constraint analysis.

VarStatus classifies each field as BOUND (value known at analysis time),
OPEN (value to be computed), or PARTIAL (some bits known, some free).

VarStatusMap is built from the IR struct type's fields once per action class
and evolved during the iterative closure algorithm.
"""
from __future__ import annotations

import enum
import dataclasses
from typing import Dict, List, Optional, Set


class VarStatus(enum.Enum):
    """Classification of a variable in the deterministic analysis."""
    BOUND   = "bound"    # Value is known at analysis entry (input, comp field)
    OPEN    = "open"     # Value must be computed by the closure
    PARTIAL = "partial"  # Some bits known, some free — conservative DEFERRED


@dataclasses.dataclass
class VarInfo:
    """Per-variable metadata stored in VarStatusMap."""
    status: VarStatus
    write_back: bool  # True → emit self_obj.x = _x; False → local var only


class VarStatusMap:
    """Maps variable names to their current status during closure analysis.

    Parameters
    ----------
    initial:
        Dict of ``name → VarInfo`` built by ``build_from_struct``.  Callers
        typically use the class method rather than constructing this directly.
    """

    def __init__(self, initial: Dict[str, VarInfo]):
        self._map: Dict[str, VarInfo] = dict(initial)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def status(self, name: str) -> VarStatus:
        """Return the current status of *name*, or BOUND if unknown (safe default)."""
        info = self._map.get(name)
        return info.status if info is not None else VarStatus.BOUND

    def write_back(self, name: str) -> bool:
        """Return True if *name* should be written back to self_obj after solve."""
        info = self._map.get(name)
        return info.write_back if info is not None else False

    def is_bound(self, name: str) -> bool:
        return self.status(name) == VarStatus.BOUND

    def is_open(self, name: str) -> bool:
        return self.status(name) == VarStatus.OPEN

    def open_var_names(self) -> Set[str]:
        """Return the set of variable names currently with OPEN status."""
        return {n for n, info in self._map.items() if info.status == VarStatus.OPEN}

    def all_names(self) -> Set[str]:
        return set(self._map.keys())

    def count_open_vars_in(self, var_names: Set[str]) -> int:
        """Count how many names in *var_names* have OPEN status."""
        return sum(1 for n in var_names if self.is_open(n))

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def bind(self, name: str) -> None:
        """Transition *name* from OPEN → BOUND.  No-op if already BOUND."""
        if name in self._map:
            info = self._map[name]
            if info.status == VarStatus.OPEN:
                self._map[name] = VarInfo(VarStatus.BOUND, info.write_back)

    def partial(self, name: str) -> None:
        """Transition *name* to PARTIAL (some bits resolved)."""
        if name in self._map:
            info = self._map[name]
            if info.status == VarStatus.OPEN:
                self._map[name] = VarInfo(VarStatus.PARTIAL, info.write_back)

    def copy(self) -> "VarStatusMap":
        """Return an independent copy of this map."""
        return VarStatusMap({n: VarInfo(info.status, info.write_back)
                             for n, info in self._map.items()})

    def __repr__(self) -> str:  # pragma: no cover
        parts = [f"{n}={info.status.value}" for n, info in sorted(self._map.items())]
        return f"VarStatusMap({{{', '.join(parts)}}})"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_from_struct(struct_type, py_class=None) -> VarStatusMap:
    """Build a VarStatusMap from a ``DataTypeStruct``/``DataTypeClass``.

    Parameters
    ----------
    struct_type:
        The IR ``DataTypeStruct`` or ``DataTypeClass``.
    py_class:
        Optional Python class (the ``@dataclass``-decorated action class).
        When provided, Python-level field metadata (e.g. ``flow_ref``
        direction from ``zdc.flow_input()`` / ``zdc.flow_output()``) is
        used for classification.  Required for correct detection of
        ``flow_input`` / ``flow_output`` fields, since ``DataModelFactory``
        does not transfer this metadata to the IR.

    Detection rules (from DETERMINISTIC_CONSTRAINT_PLAN.md §2.1):

    +-------------------------------------------+---------------------+-----------+
    | Field declaration                         | Initial status      | Write-back|
    +===========================================+=====================+===========+
    | ``zdc.input()``  (FieldInOut, is_out=F)  | BOUND               | no        |
    | ``flow_input()`` (metadata kind=flow_ref, | BOUND               | no        |
    |   direction=input)                        |                     |           |
    | Non-rand comp/struct field                | BOUND               | no        |
    | ``zdc.reg()`` / ``Reg[T]``                | BOUND (cur value)   | yes — reg |
    | ``zdc.rand()`` / ``zdc.randc()``          | OPEN                | yes       |
    | ``zdc.output()`` (FieldInOut, is_out=T)  | OPEN                | yes       |
    | ``flow_output()`` (metadata kind=flow_ref,| OPEN                | yes       |
    |   direction=output)                       |                     |           |
    | ``field(internal=True)`` / leading ``_`` | OPEN                | no        |
    +-------------------------------------------+---------------------+-----------+
    """
    import dataclasses as dc
    from zuspec.ir.core.fields import FieldInOut

    # Build a name→metadata dict from the Python class if available.
    py_field_meta: Dict[str, dict] = {}
    if py_class is not None and hasattr(py_class, '__dataclass_fields__'):
        try:
            for pyf in dc.fields(py_class):
                if pyf.metadata:
                    py_field_meta[pyf.name] = dict(pyf.metadata)
        except TypeError:
            pass  # non-dataclass or fields() failed

    initial: Dict[str, VarInfo] = {}

    for field in struct_type.fields:
        name = field.name

        # ---- Detect field kind ----------------------------------------
        is_input_port = isinstance(field, FieldInOut) and not field.is_out
        is_output_port = isinstance(field, FieldInOut) and field.is_out
        is_reg = getattr(field, 'is_reg', False)
        rand_kind = getattr(field, 'rand_kind', None)

        # flow_input / flow_output: prefer Python-class metadata (always correct)
        # then fall back to IR metadata (may be None if DataModelFactory didn't copy it)
        py_meta = py_field_meta.get(name) or _get_dc_metadata(field)
        dc_kind      = py_meta.get('kind', '')
        dc_direction = py_meta.get('direction', '')
        is_flow_input  = (dc_kind == 'flow_ref' and dc_direction == 'input')
        is_flow_output = (dc_kind == 'flow_ref' and dc_direction == 'output')
        is_internal = py_meta.get('internal', False) or name.startswith('_')

        # ---- Assign initial status ------------------------------------
        if is_flow_input or is_input_port:
            # Known at entry — BOUND, no write-back
            initial[name] = VarInfo(VarStatus.BOUND, False)

        elif is_reg:
            # Register current value is BOUND; next value is computed (write-back)
            initial[name] = VarInfo(VarStatus.BOUND, True)

        elif rand_kind is not None:
            # rand / randc — always written back (body() may read the field).
            # Only suppress write-back when the field has EXPLICIT internal=True
            # metadata (e.g. zdc.field(internal=True)), not merely a leading '_'
            # name convention, because leading-'_' rand fields like _alu_out are
            # private solver temporaries whose values the body() still needs.
            explicit_internal = bool(py_meta.get('internal', False))
            initial[name] = VarInfo(VarStatus.OPEN, not explicit_internal)

        elif is_flow_output or is_output_port:
            # Output — must be computed
            initial[name] = VarInfo(VarStatus.OPEN, True)
            # Expand nested Buffer[T] payload fields so that dotted-path
            # constraints like ``assert self.out.t.result == x`` are recognised
            # as assignments (OPEN) rather than precondition checks (BOUND).
            if py_class is not None and is_output_port:
                _expand_buffer_payload_vars(py_class, name, initial)

        else:
            # Non-rand comp/struct field — BOUND, no write-back
            initial[name] = VarInfo(VarStatus.BOUND, False)

    return VarStatusMap(initial)


def _get_dc_metadata(field) -> dict:
    """Extract the dataclasses field metadata dict from a struct Field.

    The IR ``Field`` stores dataclass metadata in ``field.metadata`` when
    available (populated by DataModelFactory from the original Python
    dataclass field).  Returns an empty dict if not present.
    """
    # Try to get from field.metadata (may be a mappingproxy or dict)
    md = getattr(field, 'metadata', None)
    if md is not None and hasattr(md, 'get'):
        return md
    return {}


def _expand_buffer_payload_vars(
    py_class: type,
    field_name: str,
    initial: Dict[str, "VarInfo"],
) -> None:
    """Register ``"field.t.subfield"`` paths as OPEN for a Buffer[T] output field.

    Constraints use ``self.out.t.result`` syntax, resolving to ``"out.t.result"``.
    Without this expansion, those paths default to BOUND in the VarStatusMap and
    the constraint analyser incorrectly treats them as precondition checks.
    """
    import dataclasses as dc
    import typing as _typing

    try:
        for pyf in dc.fields(py_class):
            if pyf.name != field_name:
                continue
            args = _typing.get_args(pyf.type)
            if not args or not isinstance(args[0], type) or not dc.is_dataclass(args[0]):
                return
            payload_cls = args[0]
            for payload_field in dc.fields(payload_cls):
                if payload_field.metadata.get('rand', False):
                    nested_name = f"{field_name}.t.{payload_field.name}"
                    initial[nested_name] = VarInfo(VarStatus.OPEN, True)
            return
    except (TypeError, Exception):
        pass
