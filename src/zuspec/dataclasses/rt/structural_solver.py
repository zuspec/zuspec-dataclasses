"""Structural inference solver (Phase S).

Resolves unbound flow-object inputs on an action by selecting candidate
producer action types from the ICL table and determining their ordering
relative to the consumer.

LRM ordering rules (§5.4, §16.4.3):
  - Buffer / State inputs  → producer must execute **before** consumer (sequential)
  - Stream inputs          → producer executes **concurrently** with consumer
"""
from __future__ import annotations

import dataclasses as dc
import random
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .icl_table import ICLTable, ICLEntry
    from .action_context import ActionContext
    from .action_registry import ActionRegistry


class InferenceFeasibilityError(RuntimeError):
    """Raised when no ICL candidate exists for an unbound slot."""


class InferenceLimitError(RuntimeError):
    """Raised when the DFS depth limit is exceeded during inference."""


@dc.dataclass
class InferredAction:
    """An action type inferred to satisfy a consumer's unbound flow slot."""
    action_type: type
    """The action type to instantiate as producer."""
    ordering: Literal["sequential_before", "concurrent"]
    """How to schedule the inferred action relative to the consumer."""
    output_field: str
    """Field name on the producer that supplies the flow object."""
    input_field: str
    """Field name on the consumer that receives the flow object."""
    flow_obj_type: type
    """The shared flow-object type."""
    src_state: Optional[tuple] = None
    """Source state tuple for state-chain edges (None for buffer inference)."""
    dst_state: Optional[tuple] = None
    """Destination state tuple for state-chain edges (None for buffer inference)."""


class StructuralSolver:
    """Resolves unbound flow-object inputs by searching the ICL table.

    A depth-first search selects one ICL candidate per unbound slot.
    Cycles are prevented by tracking types already in the current search path.

    Args:
        icl_table: Pre-built ICL table from :class:`ICLTable.build`.
        max_depth: Maximum recursion depth for multi-level inference chains.
        seed: Optional RNG seed for reproducible candidate selection.
    """

    def __init__(
        self,
        icl_table: "ICLTable",
        max_depth: int = 5,
        seed: Optional[int] = None,
        registry: Optional["ActionRegistry"] = None,
    ) -> None:
        self._icl = icl_table
        self._max_depth = max_depth
        self._rng = random.Random(seed)
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        consumer_type: type,
        unbound_slots: List[Tuple[str, type]],
        ctx: "ActionContext",
        inline_constraints: Optional[list] = None,
    ) -> List[InferredAction]:
        """Return inferred actions needed to satisfy *consumer_type*'s unbound slots.

        Args:
            consumer_type: The action type with unbound flow-input fields.
            unbound_slots: List of ``(field_name, flow_obj_type)`` tuples.
            ctx: Current traversal context (used for cycle tracking).
            inline_constraints: Optional AST constraint statements from a
                ``with`` block, used to extract state-target predicates.

        Returns:
            Ordered list of :class:`InferredAction` instances.  Sequential
            producers come before the consumer; concurrent producers run
            alongside it.

        Raises:
            InferenceFeasibilityError: No candidate exists for a slot.
            InferenceLimitError: DFS depth limit exceeded.
        """
        return self._solve_recursive(
            consumer_type=consumer_type,
            unbound_slots=unbound_slots,
            depth=0,
            seen={consumer_type},
            inline_constraints=inline_constraints,
        )

    # ------------------------------------------------------------------
    # Internal DFS
    # ------------------------------------------------------------------

    def _solve_recursive(
        self,
        consumer_type: type,
        unbound_slots: List[Tuple[str, type]],
        depth: int,
        seen: Set[type],
        inline_constraints: Optional[list] = None,
    ) -> List[InferredAction]:
        if depth > self._max_depth:
            raise InferenceLimitError(
                f"Structural inference depth limit ({self._max_depth}) exceeded "
                f"while resolving {consumer_type.__name__}"
            )

        result: List[InferredAction] = []

        for field_name, flow_obj_type in unbound_slots:
            # State-chain inference: if the flow type is a State subclass
            # and we have a registry, delegate to BFS-based state-chain solver.
            from ..types import State
            try:
                is_state = isinstance(flow_obj_type, type) and issubclass(flow_obj_type, State)
            except TypeError:
                is_state = False

            if is_state and self._registry is not None:
                state_actions = self._solve_state_chain(
                    consumer_type, field_name, flow_obj_type,
                    inline_constraints=inline_constraints,
                )
                result.extend(state_actions)
                continue

            candidates = self._icl.candidates(consumer_type, field_name)
            if not candidates:
                raise InferenceFeasibilityError(
                    f"No ICL candidate found for "
                    f"{consumer_type.__name__}.{field_name} "
                    f"(flow type: {flow_obj_type.__name__})"
                )

            # Filter out types already in the current search path (cycle guard)
            available = [c for c in candidates if c.action_type not in seen]
            if not available:
                raise InferenceFeasibilityError(
                    f"All ICL candidates for "
                    f"{consumer_type.__name__}.{field_name} "
                    f"form a cycle: {[c.action_type.__name__ for c in candidates]}"
                )

            # Choose one candidate (random for variety; deterministic via seed)
            entry = self._rng.choice(available)

            ordering = _ordering_for_flow_type(flow_obj_type)
            ia = InferredAction(
                action_type=entry.action_type,
                ordering=ordering,
                output_field=entry.output_field,
                input_field=field_name,
                flow_obj_type=flow_obj_type,
            )

            # Recursively resolve any unbound slots the inferred action itself has
            sub_unbound = _find_unbound_flow_inputs(entry.action_type, set())
            if sub_unbound:
                new_seen = seen | {entry.action_type}
                sub_actions = self._solve_recursive(
                    consumer_type=entry.action_type,
                    unbound_slots=sub_unbound,
                    depth=depth + 1,
                    seen=new_seen,
                )
                # Sub-actions must precede the inferred action
                result.extend(sub_actions)

            result.append(ia)

        return result


    # ------------------------------------------------------------------
    # State-chain BFS
    # ------------------------------------------------------------------

    def _solve_state_chain(
        self,
        consumer_type: type,
        field_name: str,
        flow_obj_type: type,
        inline_constraints: Optional[list] = None,
    ) -> List[InferredAction]:
        """Resolve a State-typed flow-input via BFS on the state graph.

        Builds (or retrieves from cache) the state graph, determines the
        current state, extracts a target predicate from inline constraints,
        and runs BFS to find the shortest transition chain.
        """
        from .state_graph_factory import get_or_build

        graph = get_or_build(flow_obj_type, self._registry)

        # Determine current state (all-zeros if initial)
        current = graph.initial_state()

        # Extract target predicate from inline constraints
        target_pred = extract_state_target(
            inline_constraints, field_name, flow_obj_type,
        )

        if target_pred is None:
            # No state-specific constraints: no transitions needed
            return []

        # BFS from current to any node satisfying target_pred
        path = self._bfs(graph, current, target_pred)
        if path is None:
            raise InferenceFeasibilityError(
                f"No path from {current} to a state satisfying inline "
                f"constraints on {consumer_type.__name__}.{field_name}"
            )

        # Convert path edges to InferredAction list
        result: List[InferredAction] = []
        for edge in path:
            input_f = _find_flow_field(edge.action_type, flow_obj_type, "input")
            output_f = _find_flow_field(edge.action_type, flow_obj_type, "output")
            result.append(InferredAction(
                action_type=edge.action_type,
                ordering="sequential_before",
                output_field=output_f,
                input_field=field_name,
                flow_obj_type=flow_obj_type,
                src_state=edge.src,
                dst_state=edge.dst,
            ))
        return result

    def _bfs(self, graph, start: tuple, predicate) -> Optional[list]:
        """Standard BFS on StateGraph; returns shortest path as list of StateEdge."""
        from collections import deque
        if predicate(start):
            return []
        visited = {start}
        queue = deque([(start, [])])
        while queue:
            node, path = queue.popleft()
            for edge in graph.edges.get(node, []):
                if edge.dst in visited:
                    continue
                new_path = path + [edge]
                if predicate(edge.dst):
                    return new_path
                visited.add(edge.dst)
                queue.append((edge.dst, new_path))
        return None


# ---------------------------------------------------------------------------
# State-target extraction from inline constraint ASTs
# ---------------------------------------------------------------------------

def extract_state_target(
    inline_constraints: Optional[list],
    field_name: str,
    state_type: type,
) -> Optional[Callable]:
    """Parse inline constraint ASTs to extract field-level predicates on the state.

    Looks for patterns like ``label.field_name.state_field == value`` and builds
    a combined predicate over state value-tuples.

    Returns None if no state-specific constraints are found.
    """
    import ast as _ast
    import dataclasses as _dc

    if not inline_constraints:
        return None

    # Map state field names to tuple indices
    try:
        fields = _dc.fields(state_type)
    except TypeError:
        return None

    rand_fields: List[Tuple[str, int]] = []
    idx = 0
    for f in fields:
        meta = f.metadata or {}
        if meta.get("rand"):
            rand_fields.append((f.name, idx))
            idx += 1

    field_index_map = dict(rand_fields)

    predicates: List[Callable] = []

    for stmt in inline_constraints:
        # Unwrap ast.Expr
        expr = stmt
        if isinstance(expr, _ast.Expr):
            expr = expr.value

        _extract_predicates_from_expr(
            expr, field_name, field_index_map, predicates,
        )

    if not predicates:
        return None

    def combined(t: tuple) -> bool:
        return all(p(t) for p in predicates)

    return combined


def _extract_predicates_from_expr(
    expr,
    field_name: str,
    field_index_map: Dict[str, int],
    predicates: list,
) -> None:
    """Extract comparison predicates from a single AST expression node."""
    import ast as _ast
    import operator

    if not isinstance(expr, _ast.Compare):
        return

    # Pattern: label.flow_field.state_field op constant
    # or: self.flow_field.state_field op constant
    left = expr.left
    state_field_name = None
    if isinstance(left, _ast.Attribute):
        attr_name = left.attr
        val = left.value
        # Check: val is Attribute(value=Name(id=...), attr=field_name)
        if (isinstance(val, _ast.Attribute) and val.attr == field_name):
            state_field_name = attr_name
        # Also check: val is Name and attr is a state field (self.state_field pattern)
        elif isinstance(val, _ast.Name):
            # label.state_field -- but this only works if field_name matches
            # In anon traversal with label: label.flow_field.state_field
            pass

    if state_field_name is None:
        return

    if state_field_name not in field_index_map:
        return

    field_idx = field_index_map[state_field_name]

    # Process each comparison operation
    op_map = {
        _ast.Eq: operator.eq,
        _ast.NotEq: operator.ne,
        _ast.Lt: operator.lt,
        _ast.LtE: operator.le,
        _ast.Gt: operator.gt,
        _ast.GtE: operator.ge,
    }

    for op_node, comparator in zip(expr.ops, expr.comparators):
        if not isinstance(comparator, _ast.Constant):
            continue
        op_type = type(op_node)
        if op_type not in op_map:
            continue
        op_fn = op_map[op_type]
        const_val = comparator.value

        # Capture in closure
        def make_pred(idx, fn, val):
            return lambda t: fn(t[idx], val)

        predicates.append(make_pred(field_idx, op_fn, const_val))


def _find_flow_field(action_type: type, flow_obj_type: type, direction: str) -> str:
    """Find the field name on action_type for the given flow type and direction."""
    try:
        fields = dc.fields(action_type)
    except TypeError:
        raise InferenceFeasibilityError(
            f"Cannot find flow {direction} field on {action_type.__name__}"
        )

    ann: Dict[str, Any] = {}
    for klass in action_type.__mro__:
        ann.update(klass.__dict__.get("__annotations__", {}))

    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref":
            continue
        if meta.get("direction") != direction:
            continue
        ftype = ann.get(f.name)
        if isinstance(ftype, type):
            try:
                if ftype is flow_obj_type or issubclass(ftype, flow_obj_type):
                    return f.name
            except TypeError:
                pass

    raise InferenceFeasibilityError(
        f"No flow {direction} field of type {flow_obj_type.__name__} "
        f"on {action_type.__name__}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordering_for_flow_type(flow_obj_type: type) -> Literal["sequential_before", "concurrent"]:
    """Return the required scheduling relationship for a given flow type."""
    from ..types import Stream
    try:
        if issubclass(flow_obj_type, Stream):
            return "concurrent"
    except TypeError:
        pass
    return "sequential_before"


def _find_unbound_flow_inputs(
    action_type: type,
    already_bound: Set[str],
) -> List[Tuple[str, type]]:
    """Return (field_name, flow_obj_type) tuples for unbound flow-input fields.

    A flow-input field is *unbound* when it is not already present in
    *already_bound* (i.e., not yet provided by the current flow-binding context).
    """
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return []

    ann: Dict[str, Any] = {}
    for klass in action_type.__mro__:
        ann.update(klass.__dict__.get("__annotations__", {}))

    result = []
    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref":
            continue
        if meta.get("direction") != "input":
            continue
        if f.name in already_bound:
            continue
        flow_obj_type = ann.get(f.name)
        if isinstance(flow_obj_type, type):
            result.append((f.name, flow_obj_type))
    return result
