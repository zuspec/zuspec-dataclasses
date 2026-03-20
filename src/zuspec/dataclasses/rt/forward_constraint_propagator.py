"""Forward constraint propagation for sequential action chains.

After a sequential action's ``body()`` completes, its concrete field values
are recorded.  Before the *next* sequential action's ``randomize()`` call,
``label.field`` references in inline constraints are replaced by their
concrete values via AST substitution.

This covers cross-action constraints of the form::

    with do(ActionB) as b:
        assert b.out_val == a.in_val + 1

where ``in_val`` is a *local rand field* of the predecessor action ``a``,
known concretely only after ``a`` completes.  The propagator substitutes the
concrete value of ``a.in_val`` into the constraint AST before ActionB's solve,
turning it into a simple equality like ``assert self.out_val == 43``.

**Scope**: sequential pairs within the same sequence block only.
Cross-branch propagation is Phase P4.
"""
from __future__ import annotations

import ast
import copy
import dataclasses as dc
from typing import Any, Dict, List, Optional


class ForwardConstraintPropagator:
    """Records concrete field values from completed sequential actions and
    substitutes ``label.field`` references in subsequent actions' inline
    constraints.

    Lifecycle per sequence block::

        propagator = ForwardConstraintPropagator()
        # For each sequential statement:
        #   1. rewritten = propagator.substitute(inline_constraints)
        #   2. traverse action with rewritten constraints
        #   3. propagator.record_completed(action, label)
    """

    def __init__(self) -> None:
        # label -> {field_name: concrete_value}
        self._values: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_completed(self, action: Any, label: Optional[str] = None) -> None:
        """Store all concrete scalar rand-field values of *action*.

        Args:
            action: The action instance that just finished ``body()``.
            label: Activity-level label (handle name); when ``None``, uses
                   ``type(action).__name__``.
        """
        key = label or type(action).__name__
        try:
            fields = dc.fields(action)
        except TypeError:
            return
        values: Dict[str, Any] = {}
        for f in fields:
            val = getattr(action, f.name, None)
            meta = f.metadata or {}
            if meta.get("kind") in ("flow_ref", "resource_ref"):
                continue
            if f.name == "comp":
                continue
            if val is None:
                continue
            if isinstance(val, (int, float, bool, str)):
                values[f.name] = val
        if values:
            self._values[key] = values

    # ------------------------------------------------------------------
    # Constraint substitution
    # ------------------------------------------------------------------

    def substitute(self, stmts: List[ast.stmt]) -> List[ast.stmt]:
        """Return a copy of *stmts* with ``label.field`` references replaced
        by their concrete values from completed actions.

        For example, if action ``a`` completed with ``in_val = 42``, then
        ``a.in_val + 1`` is replaced by ``42 + 1`` in the AST.

        Returns the original list unchanged when there are no recorded values.
        """
        if not self._values:
            return stmts
        substitutor = _CrossActionSubstitutor(self._values)
        result = []
        for s in stmts:
            s2 = substitutor.visit(copy.deepcopy(s))
            ast.fix_missing_locations(s2)
            result.append(s2)
        return result

    def clear(self) -> None:
        """Discard all recorded values (e.g., at end of a sequence block)."""
        self._values.clear()


# ---------------------------------------------------------------------------
# AST substitutor
# ---------------------------------------------------------------------------

class _CrossActionSubstitutor(ast.NodeTransformer):
    """Replace ``label.field`` AST attribute accesses with constant values.

    Given ``values = {"a": {"in_val": 42}}``:
      - ``a.in_val``        -> ``42``
      - ``a.in_val + 1``    -> ``42 + 1``  (evaluated by the solver's eval)
      - ``b.out_val``       -> unchanged (no entry for ``b``)
    """

    def __init__(self, values: Dict[str, Dict[str, Any]]) -> None:
        self._values = values

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.value, ast.Name):
            return node
        label = node.value.id
        field = node.attr
        if label in self._values and field in self._values[label]:
            val = self._values[label][field]
            if isinstance(val, bool):
                return ast.Constant(value=int(val))
            return ast.Constant(value=val)
        return node
