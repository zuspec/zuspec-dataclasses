"""ConstraintEvalPlan — result of static deterministic constraint analysis.

A ConstraintEvalPlan describes, for a single action class, the ordered
sequence of operations needed to evaluate all constraints without invoking
a solver:

1. Precondition checks  (fail fast on illegal inputs)
2. Assignments          (sequenced, topological order)
3. Write-back           (filtered to non-internal OPEN fields)
4. Postcondition checks (optional, enabled by ZDC_DETERMINISTIC_DEBUG)
"""
from __future__ import annotations

import dataclasses
from typing import List, Optional, Dict, Tuple


# Forward reference — eval_expr is imported lazily to avoid circular deps
# at module load time.  Type annotations use string literals.


@dataclasses.dataclass
class CheckNode:
    """A condition that must hold (precondition or postcondition).

    Parameters
    ----------
    expr:
        EvalExpr that evaluates to a boolean (int: 0 = false, non-zero = true).
    source_loc:
        Human-readable description of the constraint origin, e.g.
        ``"Decode.c_valid_opcode line 42"``.
    """
    expr: "EvalExpr"
    source_loc: str


@dataclasses.dataclass
class AssignNode:
    """An assignment of a computed value to a variable.

    Parameters
    ----------
    var_name:
        Name of the variable being assigned.
    expr:
        EvalExpr that computes the value.
    checks:
        Side-conditions to emit as precondition checks alongside this
        assignment (e.g. divisibility check for ``x * k == C``).
    source_loc:
        Human-readable description of the originating constraint.
    write_back:
        True → emit ``self_obj.<var_name> = <value>`` after computation.
        False → keep as a local variable (internal/leading-_ fields).
    """
    var_name: str
    expr: "EvalExpr"
    checks: List[CheckNode]
    source_loc: str
    write_back: bool


@dataclasses.dataclass
class CoverageGap:
    """A missing key in a selector lookup table.

    Reported when a ``_detect_selector_groups`` run finds that some key
    values have no entry in the generated ExprLookup table.
    """
    variable: str
    missing_keys: List[Tuple]  # Each element is a key tuple (or scalar)
    source_loc: str


@dataclasses.dataclass
class ConstraintEvalPlan:
    """Complete deterministic evaluation plan for one action class.

    Parameters
    ----------
    action_class:
        The Python class this plan was built for.
    preconditions:
        CheckNodes sourced from *requires*-role constraints plus any body
        constraint that had 0 OPEN variables at analysis entry.
    assignments:
        AssignNodes in topological order (each assigned variable is BOUND
        before it is used by a later assignment).
    postconditions:
        CheckNodes sourced from *ensures*-role constraints plus any body
        constraint that had 0 OPEN variables *after* the closure completed.
    underdetermined:
        Names of OPEN variables that could not be resolved (design error).
        If non-empty, the plan should NOT be used — fall back to the solver.
    bound_paths:
        Sorted list of dotted field paths that appear as ExprVar references
        to BOUND variables.  Used by PythonFunctionEmitter to emit one
        ``_p_<mangled>`` local per path at the function top, eliminating
        repeated ``getattr`` calls.
    coverage_gaps:
        Coverage gap reports from selector-pattern detection.
    lookup_tables:
        Dict mapping table_name → {key: value} for ExprLookup nodes.
        These are emitted as module-level dict literals by the Python emitter.
    """
    action_class: type
    preconditions:   List[CheckNode]
    assignments:     List[AssignNode]
    postconditions:  List[CheckNode]
    underdetermined: List[str]
    bound_paths:     List[str]
    coverage_gaps:   List[CoverageGap] = dataclasses.field(default_factory=list)
    lookup_tables:   Dict[str, dict] = dataclasses.field(default_factory=dict)
