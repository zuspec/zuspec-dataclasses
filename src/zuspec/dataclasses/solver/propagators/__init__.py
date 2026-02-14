"""Constraint propagators."""

from .base import Propagator, PropagationResult, PropagationStatus
from .arithmetic import (
    AddPropagator,
    SubPropagator,
    MultPropagator,
    DivPropagator,
    ModPropagator,
)
from .relational import (
    EqualPropagator,
    NotEqualPropagator,
    LessThanPropagator,
    LessEqualPropagator,
    GreaterThanPropagator,
    GreaterEqualPropagator,
)
from .implication import (
    ImplicationPropagator,
    ConditionalImplicationPropagator,
)
from .set_membership import (
    InSetPropagator,
    RangeConstraintPropagator,
)
from .uniqueness import (
    UniquePropagator,
    PairwiseUniquePropagator,
)
from .conditional import (
    ConditionalConstraint,
    TernaryExpressionPropagator,
)
from .foreach import (
    ForeachExpander,
    ForeachConstraintGroup,
    create_array_constraint_foreach,
    create_unique_array_foreach,
)
from .functions import (
    CountOnesPropagator,
    Clog2Propagator,
    UserFunctionPropagator,
)

__all__ = [
    # Base classes
    "Propagator",
    "PropagationResult",
    "PropagationStatus",
    # Arithmetic
    "AddPropagator",
    "SubPropagator",
    "MultPropagator",
    "DivPropagator",
    "ModPropagator",
    # Relational
    "EqualPropagator",
    "NotEqualPropagator",
    "LessThanPropagator",
    "LessEqualPropagator",
    "GreaterThanPropagator",
    "GreaterEqualPropagator",
    # Implication
    "ImplicationPropagator",
    "ConditionalImplicationPropagator",
    # Set membership
    "InSetPropagator",
    "RangeConstraintPropagator",
    # Uniqueness
    "UniquePropagator",
    "PairwiseUniquePropagator",
    # Conditional
    "ConditionalConstraint",
    "TernaryExpressionPropagator",
    # Foreach
    "ForeachExpander",
    "ForeachConstraintGroup",
    "create_array_constraint_foreach",
    "create_unique_array_foreach",
    # Functions
    "CountOnesPropagator",
    "Clog2Propagator",
    "UserFunctionPropagator",
]
