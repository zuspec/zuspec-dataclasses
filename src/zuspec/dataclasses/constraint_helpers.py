#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""Helper functions for constraint expressions.

These functions are used within @constraint decorated methods and are
parsed from AST - they are never actually executed.
"""
from typing import Any, Dict, List, Union, Tuple


class _ConstraintMarker:
    """Base class for constraint expression markers that are parsed from AST."""
    pass


class _ImpliesExpr(_ConstraintMarker):
    """Marker for implication constraint: antecedent -> consequent."""
    def __init__(self, antecedent: Any, consequent: Any):
        self.antecedent = antecedent
        self.consequent = consequent


class _DistExpr(_ConstraintMarker):
    """Marker for distribution constraint."""
    def __init__(self, var: Any, weights: Dict[Any, Union[int, Tuple[int, str]]]):
        self.var = var
        self.weights = weights


class _UniqueExpr(_ConstraintMarker):
    """Marker for uniqueness constraint."""
    def __init__(self, vars: List[Any]):
        self.vars = vars


class _SolveOrderExpr(_ConstraintMarker):
    """Marker for solve ordering constraint."""
    def __init__(self, *vars):
        self.vars = vars


def implies(antecedent: Any, consequent: Any) -> _ImpliesExpr:
    """Implication constraint: if antecedent is true, consequent must be true.
    
    This is logically equivalent to: (not antecedent) or consequent
    
    Example:
        @constraint
        def addr_implications(self):
            implies(self.addr_type == 0, self.addr < 16)
            implies(self.addr_type == 1, 16 <= self.addr < 128)
    
    Args:
        antecedent: Condition that triggers the implication
        consequent: Condition that must hold when antecedent is true
        
    Returns:
        ImpliesExpr marker (never actually executed)
    """
    return _ImpliesExpr(antecedent, consequent)


def dist(var: Any, weights: Dict[Any, Union[int, Tuple[int, str]]]) -> _DistExpr:
    """Distribution constraint: assign weights to values or ranges.
    
    Example:
        @constraint
        def type_distribution(self):
            dist(self.pkt_type, {
                0: 40,           # Type 0: weight 40
                1: 30,           # Type 1: weight 30
                2: 20,           # Type 2: weight 20
                3: 10            # Type 3: weight 10
            })
        
        @constraint
        def addr_distribution(self):
            dist(self.addr, {
                range(0, 16): (16, 'per_value'),      # 16 weight per value
                range(16, 128): (112, 'total'),       # 112 total weight
                range(128, 256): (128, 'per_value')   # 128 weight per value
            })
    
    Args:
        var: Variable to constrain
        weights: Dict mapping values/ranges to weights.
                 Values can be:
                 - int: absolute weight for discrete value
                 - tuple(int, str): (weight, 'per_value') or (weight, 'total')
        
    Returns:
        DistExpr marker (never actually executed)
    """
    return _DistExpr(var, weights)


def unique(vars: List[Any]) -> _UniqueExpr:
    """Uniqueness constraint: all variables must have different values.
    
    Example:
        @constraint
        def all_unique(self):
            unique([self.id1, self.id2, self.id3])
    
    Args:
        vars: List of variables that must be unique
        
    Returns:
        UniqueExpr marker (never actually executed)
    """
    return _UniqueExpr(vars)


def solve_order(*vars) -> _SolveOrderExpr:
    """Solve ordering constraint: variables should be solved in specified order.
    
    Example:
        @constraint
        def addr_data_relation(self):
            solve_order(self.addr, self.data)
            self.data == self.addr * 2
        
        @constraint
        def pipeline_order(self):
            solve_order(self.stage1, self.stage2, self.stage3)
    
    Args:
        *vars: Variables in solve order (first is solved first)
        
    Returns:
        SolveOrderExpr marker (never actually executed)
    """
    return _SolveOrderExpr(*vars)


# Export all public symbols
__all__ = [
    'implies',
    'dist',
    'unique',
    'solve_order',
]
