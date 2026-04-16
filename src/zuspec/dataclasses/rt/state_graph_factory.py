"""Automatic state-graph construction from State type definitions.

Given a ``State`` subclass and an ``ActionRegistry``, this module builds a
directed graph where:

- **Nodes** are valid state value-tuples (the cartesian product of field
  domains filtered by the state's constraints).
- **Edges** represent transition actions: an action type that has both
  ``flow_input`` and ``flow_output`` of the same ``State`` type.

The graph is cached per ``State`` type and used by the ``StructuralSolver``
to perform BFS-based state-chain inference.
"""
from __future__ import annotations

import ast as _ast
import dataclasses as dc
import inspect
import itertools
import textwrap
import threading
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .action_registry import ActionRegistry

from ..types import SignWidth, U, S


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class StateSpaceTooLargeError(RuntimeError):
    """Raised when the cartesian product of state field domains exceeds the limit."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dc.dataclass
class FieldDescriptor:
    """Describes one rand field on a State subclass."""
    name: str
    index: int
    lo: int
    hi: int
    signed: bool


@dc.dataclass
class StateEdge:
    """A directed edge in the state graph."""
    src: tuple
    dst: tuple
    action_type: type


@dc.dataclass
class StateGraph:
    """Directed graph of valid state value-tuples connected by transition actions."""
    state_type: type
    field_descriptors: List[FieldDescriptor]
    nodes: List[tuple]
    node_set: Set[tuple]
    edges: Dict[tuple, List[StateEdge]]

    def initial_state(self) -> tuple:
        """Return the all-zeros initial state (default-constructed)."""
        return tuple(0 for _ in self.field_descriptors)


# ---------------------------------------------------------------------------
# Field discovery
# ---------------------------------------------------------------------------

def _get_annotations(cls: type) -> Dict[str, Any]:
    """Merge annotations across MRO."""
    ann: Dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        ann.update(klass.__dict__.get("__annotations__", {}))
    return ann


def _fields_from_state_type(state_type: type) -> List[FieldDescriptor]:
    """Inspect a State subclass and return descriptors for its rand fields.

    Raises TypeError for fields whose domain cannot be determined.
    """
    from typing import get_origin, get_args, Annotated

    try:
        fields = dc.fields(state_type)
    except TypeError:
        return []

    ann = _get_annotations(state_type)
    result: List[FieldDescriptor] = []
    idx = 0

    for f in fields:
        meta = f.metadata or {}
        if not meta.get("rand"):
            continue

        hint = ann.get(f.name)
        lo: Optional[int] = None
        hi: Optional[int] = None
        signed = False

        # Check for explicit domain in metadata
        domain = meta.get("domain")
        if domain is not None and isinstance(domain, tuple) and len(domain) == 2:
            lo, hi = domain

        # Check Annotated[int, U(n)] / Annotated[int, S(n)] type hints
        if lo is None and hint is not None:
            if get_origin(hint) is Annotated:
                args = get_args(hint)
                for a in args[1:]:
                    if isinstance(a, SignWidth):
                        w = a.width
                        signed = a.signed
                        if signed:
                            lo = -(1 << (w - 1))
                            hi = (1 << (w - 1)) - 1
                        else:
                            lo = 0
                            hi = (1 << w) - 1
                        break

        if lo is None or hi is None:
            raise TypeError(
                f"State field '{state_type.__name__}.{f.name}' has no bounded "
                f"domain. Use a sized type (e.g. zdc.u2) or rand(domain=(lo,hi))."
            )

        result.append(FieldDescriptor(
            name=f.name, index=idx, lo=lo, hi=hi, signed=signed,
        ))
        idx += 1

    return result


# ---------------------------------------------------------------------------
# State invariant (AST-based evaluation)
# ---------------------------------------------------------------------------

def _state_invariant(state_type: type, field_descs: List[FieldDescriptor]) -> Callable[[tuple], bool]:
    """Build a predicate that tests whether a value-tuple satisfies all
    constraints on the State class.

    Parses constraint method source into AST and evaluates it directly
    against candidate value-tuples using a lightweight interpreter.
    """
    constraint_asts = _collect_constraint_asts(state_type)

    if not constraint_asts:
        return lambda t: True

    def predicate(t: tuple) -> bool:
        ns = {fd.name: t[fd.index] for fd in field_descs}
        for ast_node in constraint_asts:
            if not _eval_constraint_ast(ast_node, ns):
                return False
        return True

    return predicate


def _collect_constraint_asts(state_type: type) -> list:
    """Parse constraint method bodies into AST expressions."""
    result = []
    seen_names: set = set()

    for klass in state_type.__mro__:
        for name, member in klass.__dict__.items():
            if not callable(member):
                continue
            if not getattr(member, "_is_constraint", False):
                continue
            if name in seen_names:
                continue
            seen_names.add(name)

            try:
                source = textwrap.dedent(inspect.getsource(member))
                tree = _ast.parse(source, mode="exec")
            except Exception:
                continue

            if tree.body and isinstance(tree.body[0], _ast.FunctionDef):
                for stmt in tree.body[0].body:
                    result.append(stmt)

    return result


def _eval_constraint_ast(node, ns: dict) -> bool:
    """Evaluate a single constraint AST statement against namespace *ns*."""
    if isinstance(node, _ast.Expr):
        return _eval_constraint_ast(node.value, ns)

    if isinstance(node, _ast.Compare):
        left_val = _eval_expr(node.left, ns)
        for op, comparator in zip(node.ops, node.comparators):
            right_val = _eval_expr(comparator, ns)
            if not _eval_cmp(left_val, right_val, op):
                return False
        return True

    if isinstance(node, _ast.Call):
        func = node.func
        func_name = None
        if isinstance(func, _ast.Name):
            func_name = func.id
        elif isinstance(func, _ast.Attribute):
            func_name = func.attr

        if func_name == "implies" and len(node.args) == 2:
            antecedent = _eval_expr(node.args[0], ns)
            if not antecedent:
                return True
            consequent = _eval_expr(node.args[1], ns)
            return bool(consequent)

    if isinstance(node, _ast.BoolOp):
        if isinstance(node.op, _ast.And):
            return all(_eval_constraint_ast(v, ns) for v in node.values)
        elif isinstance(node.op, _ast.Or):
            return any(_eval_constraint_ast(v, ns) for v in node.values)

    if isinstance(node, _ast.UnaryOp) and isinstance(node.op, _ast.Not):
        return not _eval_constraint_ast(node.operand, ns)

    # Can't evaluate -> assume satisfied
    return True


def _eval_expr(node, ns: dict):
    """Evaluate an AST expression node against namespace *ns*."""
    if isinstance(node, _ast.Constant):
        return node.value

    if isinstance(node, _ast.Name):
        return ns.get(node.id, 0)

    if isinstance(node, _ast.Attribute):
        if isinstance(node.value, _ast.Name) and node.value.id == "self":
            return ns.get(node.attr, 0)
        val = _eval_expr(node.value, ns)
        return getattr(val, node.attr, 0) if val is not None else 0

    if isinstance(node, _ast.BinOp):
        left = _eval_expr(node.left, ns)
        right = _eval_expr(node.right, ns)
        if isinstance(node.op, _ast.Add): return left + right
        if isinstance(node.op, _ast.Sub): return left - right
        if isinstance(node.op, _ast.Mult): return left * right
        if isinstance(node.op, _ast.FloorDiv): return left // right if right else 0
        if isinstance(node.op, _ast.Mod): return left % right if right else 0
        return 0

    if isinstance(node, _ast.UnaryOp):
        operand = _eval_expr(node.operand, ns)
        if isinstance(node.op, _ast.USub): return -operand
        if isinstance(node.op, _ast.Not): return not operand
        return operand

    if isinstance(node, _ast.Compare):
        left_val = _eval_expr(node.left, ns)
        for op, comparator in zip(node.ops, node.comparators):
            right_val = _eval_expr(comparator, ns)
            if not _eval_cmp(left_val, right_val, op):
                return False
            left_val = right_val
        return True

    if isinstance(node, _ast.BoolOp):
        if isinstance(node.op, _ast.And):
            return all(_eval_expr(v, ns) for v in node.values)
        elif isinstance(node.op, _ast.Or):
            return any(_eval_expr(v, ns) for v in node.values)

    if isinstance(node, _ast.Call):
        func = node.func
        func_name = None
        if isinstance(func, _ast.Name):
            func_name = func.id
        elif isinstance(func, _ast.Attribute):
            func_name = func.attr
        if func_name == "implies" and len(node.args) == 2:
            antecedent = _eval_expr(node.args[0], ns)
            if not antecedent:
                return True
            return _eval_expr(node.args[1], ns)

    return 0


def _eval_cmp(left, right, op) -> bool:
    """Evaluate a comparison operator."""
    if isinstance(op, _ast.Eq): return left == right
    if isinstance(op, _ast.NotEq): return left != right
    if isinstance(op, _ast.Lt): return left < right
    if isinstance(op, _ast.LtE): return left <= right
    if isinstance(op, _ast.Gt): return left > right
    if isinstance(op, _ast.GtE): return left >= right
    return True


# ---------------------------------------------------------------------------
# Transition action discovery
# ---------------------------------------------------------------------------

def _transition_actions_for_state(
    registry: "ActionRegistry",
    state_type: type,
) -> List[type]:
    """Return action types that have both flow_input and flow_output of *state_type*."""
    producers = set(info.action_type for info in registry.producers_for(state_type))
    consumers = set(info.action_type for info in registry.consumers_for(state_type))
    return list(producers & consumers)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph(
    state_type: type,
    registry: "ActionRegistry",
    max_states: int = 10_000,
) -> StateGraph:
    """Enumerate valid states and transition edges for *state_type*."""
    field_descs = _fields_from_state_type(state_type)

    if not field_descs:
        graph = StateGraph(
            state_type=state_type,
            field_descriptors=field_descs,
            nodes=[()],
            node_set={()},
            edges={},
        )
        return graph

    # Compute cartesian product size
    ranges = [range(fd.lo, fd.hi + 1) for fd in field_descs]
    product_size = 1
    field_contributions: List[Tuple[str, int]] = []
    for fd, r in zip(field_descs, ranges):
        sz = len(r)
        product_size *= sz
        field_contributions.append((fd.name, sz))

    if product_size > max_states:
        field_contributions.sort(key=lambda x: x[1], reverse=True)
        biggest = ", ".join(f"{n} ({s} values)" for n, s in field_contributions[:3])
        raise StateSpaceTooLargeError(
            f"State type '{state_type.__name__}' has {product_size} candidates "
            f"(limit: {max_states}). Largest contributors: {biggest}"
        )

    # Enumerate and filter by state invariant
    invariant = _state_invariant(state_type, field_descs)
    nodes: List[tuple] = []
    for combo in itertools.product(*ranges):
        if invariant(combo):
            nodes.append(combo)

    node_set = set(nodes)

    # Build edges from transition actions
    transition_types = _transition_actions_for_state(registry, state_type)
    edges: Dict[tuple, List[StateEdge]] = {}

    if transition_types:
        for action_type in transition_types:
            valid_transitions = _enumerate_transitions(
                action_type, state_type, field_descs, nodes, node_set,
            )
            for src, dst in valid_transitions:
                edges.setdefault(src, []).append(
                    StateEdge(src=src, dst=dst, action_type=action_type)
                )

    return StateGraph(
        state_type=state_type,
        field_descriptors=field_descs,
        nodes=nodes,
        node_set=node_set,
        edges=edges,
    )


def _enumerate_transitions(
    action_type: type,
    state_type: type,
    field_descs: List[FieldDescriptor],
    nodes: List[tuple],
    node_set: Set[tuple],
) -> List[Tuple[tuple, tuple]]:
    """Find all valid (src, dst) pairs for a transition action type.

    Uses AST-based evaluation of the action's constraints with prev=src
    and next=dst to determine feasibility.
    """
    # Find flow-input and flow-output field names on the action
    input_field = None
    output_field = None
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return []

    ann: Dict[str, Any] = {}
    for klass in action_type.__mro__:
        ann.update(klass.__dict__.get("__annotations__", {}))

    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref":
            continue
        ftype = ann.get(f.name)
        if not isinstance(ftype, type):
            continue
        try:
            if not issubclass(ftype, state_type):
                continue
        except TypeError:
            continue
        if meta.get("direction") == "input":
            input_field = f.name
        elif meta.get("direction") == "output":
            output_field = f.name

    if input_field is None or output_field is None:
        return []

    # Collect action constraint ASTs
    constraint_asts = _collect_constraint_asts(action_type)

    # Find action's own rand fields (non-flow)
    action_rand_fields: List[FieldDescriptor] = []
    idx = 0
    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") == "flow_ref":
            continue
        if not meta.get("rand"):
            continue
        hint = ann.get(f.name)
        lo, hi, signed = _domain_from_hint_or_meta(hint, meta)
        if lo is not None and hi is not None:
            action_rand_fields.append(
                FieldDescriptor(name=f.name, index=idx, lo=lo, hi=hi, signed=signed)
            )
            idx += 1

    result: List[Tuple[tuple, tuple]] = []

    for src in nodes:
        for dst in nodes:
            if _check_transition_feasible_ast(
                constraint_asts, field_descs,
                input_field, output_field,
                src, dst, action_rand_fields,
            ):
                result.append((src, dst))

    return result


def _domain_from_hint_or_meta(hint, meta) -> Tuple[Optional[int], Optional[int], bool]:
    """Extract domain bounds from type hint or metadata."""
    from typing import get_origin, get_args, Annotated

    lo: Optional[int] = None
    hi: Optional[int] = None
    signed = False

    domain = meta.get("domain")
    if domain is not None and isinstance(domain, tuple) and len(domain) == 2:
        lo, hi = domain
        signed = lo < 0

    if lo is None and hint is not None:
        if get_origin(hint) is Annotated:
            args = get_args(hint)
            for a in args[1:]:
                if isinstance(a, SignWidth):
                    w = a.width
                    signed = a.signed
                    if signed:
                        lo = -(1 << (w - 1))
                        hi = (1 << (w - 1)) - 1
                    else:
                        lo = 0
                        hi = (1 << w) - 1
                    break

    return lo, hi, signed


def _check_transition_feasible_ast(
    constraint_asts: list,
    field_descs: List[FieldDescriptor],
    input_field: str,
    output_field: str,
    src: tuple,
    dst: tuple,
    action_rand_fields: List[FieldDescriptor],
) -> bool:
    """Check if a transition from src to dst satisfies the action's constraints.

    For each combination of the action's own rand field values, check if all
    constraints are satisfied. If any combo works, the transition is feasible.
    """
    if not constraint_asts:
        return True

    # Build namespace with prev/next state field values accessible via
    # self.input_field.field_name and self.output_field.field_name patterns.
    # The AST references look like: self.prev.domain_A
    # We model this by providing a namespace with nested attribute access.

    class _StateProxy:
        def __init__(self, values, descs):
            for fd, v in zip(descs, values):
                object.__setattr__(self, fd.name, v)

    src_proxy = _StateProxy(src, field_descs)
    dst_proxy = _StateProxy(dst, field_descs)

    if not action_rand_fields:
        # No action rand fields: just check constraints directly
        ns = {input_field: src_proxy, output_field: dst_proxy}
        for ast_node in constraint_asts:
            if not _eval_constraint_ast(ast_node, ns):
                return False
        return True

    # Enumerate action rand field values and check if any combo satisfies
    ranges = [range(fd.lo, fd.hi + 1) for fd in action_rand_fields]
    for combo in itertools.product(*ranges):
        ns = {input_field: src_proxy, output_field: dst_proxy}
        for fd, val in zip(action_rand_fields, combo):
            ns[fd.name] = val
        ok = True
        for ast_node in constraint_asts:
            if not _eval_constraint_ast(ast_node, ns):
                ok = False
                break
        if ok:
            return True

    return False


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_STATE_GRAPH_CACHE: Dict[type, StateGraph] = {}
_CACHE_LOCK = threading.Lock()


def get_or_build(
    state_type: type,
    registry: "ActionRegistry",
    max_states: int = 10_000,
) -> StateGraph:
    """Return the cached StateGraph for *state_type*, building it if necessary."""
    with _CACHE_LOCK:
        if state_type not in _STATE_GRAPH_CACHE:
            _STATE_GRAPH_CACHE[state_type] = _build_graph(
                state_type, registry, max_states,
            )
        return _STATE_GRAPH_CACHE[state_type]


def clear_cache() -> None:
    """Clear the state graph cache (useful for testing)."""
    with _CACHE_LOCK:
        _STATE_GRAPH_CACHE.clear()
