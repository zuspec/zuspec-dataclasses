"""Function call propagators for constraint solving.

Supports PSS system functions that can appear in constraints:
- $countones(var) - count number of 1 bits
- $clog2(var) - ceiling log2 (minimum bits needed)

User-defined pure functions can also be supported if they are side-effect free.
"""

from typing import Dict, Set, Optional
import math
from ..core.variable import Variable
from ..core.domain import IntDomain
from .base import Propagator, PropagationResult, PropagationStatus


class CountOnesPropagator(Propagator):
    """
    Propagator for $countones(var) system function.
    
    Counts the number of 1 bits in the binary representation of a value.
    For example: $countones(0b1011) = 3
    
    Usage:
        result = $countones(input_var)
        
    This propagator:
    - Forward: given input domain, propagates to result
    - Backward: given result domain, can constrain input
    """
    
    def __init__(self, result_var: str, input_var: str):
        """
        Args:
            result_var: Variable to store the bit count result
            input_var: Variable whose bits to count
        """
        self.result_var = result_var
        self.input_var = input_var
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Propagate countones constraint"""
        result = variables[self.result_var]
        input_var = variables[self.input_var]
        
        changed = set()
        
        # Get the bit width of the input
        input_domain = input_var.domain
        if not isinstance(input_domain, IntDomain):
            return PropagationResult(PropagationStatus.FIXED_POINT, changed)
        
        bit_width = input_domain.width
        
        # Forward propagation: input -> result
        # The result can be at most bit_width (all 1s)
        possible_counts = set()
        for value in input_domain.values():
            bit_count = bin(value).count('1')
            possible_counts.add(bit_count)
        
        if possible_counts:
            # Create intervals for possible counts
            sorted_counts = sorted(possible_counts)
            
            # Intersect with current result domain
            new_result_intervals = []
            for count in sorted_counts:
                new_result_intervals.append((count, count))
            
            new_result_domain = IntDomain(
                new_result_intervals,
                width=result.domain.width,
                signed=result.domain.signed
            )
            
            intersected = result.domain.intersect(new_result_domain)
            if intersected.is_empty():
                return PropagationResult(PropagationStatus.CONFLICT, changed)
            
            if intersected != result.domain:
                result.domain = intersected
                changed.add(self.result_var)
        
        # Backward propagation: result -> input
        # Filter input values that don't produce valid result counts
        valid_results = set(result.domain.values())
        valid_inputs = []
        
        for value in input_domain.values():
            bit_count = bin(value).count('1')
            if bit_count in valid_results:
                valid_inputs.append(value)
        
        if not valid_inputs:
            return PropagationResult(PropagationStatus.CONFLICT, changed)
        
        # Convert to intervals
        if valid_inputs:
            new_input_intervals = []
            valid_inputs.sort()
            
            start = valid_inputs[0]
            end = valid_inputs[0]
            
            for val in valid_inputs[1:]:
                if val == end + 1:
                    end = val
                else:
                    new_input_intervals.append((start, end))
                    start = val
                    end = val
            new_input_intervals.append((start, end))
            
            new_input_domain = IntDomain(
                new_input_intervals,
                width=input_domain.width,
                signed=input_domain.signed
            )
            
            intersected = input_domain.intersect(new_input_domain)
            if intersected.is_empty():
                return PropagationResult(PropagationStatus.CONFLICT, changed)
            
            if intersected != input_domain:
                input_var.domain = intersected
                changed.add(self.input_var)
        
        status = PropagationStatus.FIXED_POINT if not changed else PropagationStatus.CONSISTENT
        return PropagationResult(status, changed)
    
    def affected_variables(self) -> Set[str]:
        """Return variables affected by this propagator"""
        return {self.result_var, self.input_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if assignment satisfies the constraint"""
        if self.result_var not in assignment or self.input_var not in assignment:
            return False
        
        result_val = assignment[self.result_var]
        input_val = assignment[self.input_var]
        
        expected_count = bin(input_val).count('1')
        return result_val == expected_count
    
    def __repr__(self) -> str:
        return f"CountOnesPropagator({self.result_var} = $countones({self.input_var}))"


class Clog2Propagator(Propagator):
    """
    Propagator for $clog2(var) system function.
    
    Computes ceiling of log base 2 - the minimum number of bits needed
    to represent the value.
    
    For example:
        $clog2(0) = 0
        $clog2(1) = 0
        $clog2(2) = 1
        $clog2(3) = 2
        $clog2(4) = 2
        $clog2(8) = 3
        $clog2(9) = 4
    
    Usage:
        result = $clog2(input_var)
    """
    
    def __init__(self, result_var: str, input_var: str):
        """
        Args:
            result_var: Variable to store the clog2 result
            input_var: Variable whose clog2 to compute
        """
        self.result_var = result_var
        self.input_var = input_var
    
    @staticmethod
    def _clog2(value: int) -> int:
        """Compute ceiling log2 of a value"""
        if value <= 0:
            return 0
        if value == 1:
            return 0
        # For values > 1, find minimum bits needed
        return (value - 1).bit_length()
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Propagate clog2 constraint"""
        result = variables[self.result_var]
        input_var = variables[self.input_var]
        
        changed = set()
        
        # Forward propagation: input -> result
        input_domain = input_var.domain
        if not isinstance(input_domain, IntDomain):
            return PropagationResult(PropagationStatus.FIXED_POINT, changed)
        
        possible_clog2s = set()
        for value in input_domain.values():
            clog2_val = self._clog2(value)
            possible_clog2s.add(clog2_val)
        
        if possible_clog2s:
            # Create intervals for possible clog2 values
            sorted_clog2s = sorted(possible_clog2s)
            
            new_result_intervals = []
            for clog2 in sorted_clog2s:
                new_result_intervals.append((clog2, clog2))
            
            new_result_domain = IntDomain(
                new_result_intervals,
                width=result.domain.width,
                signed=result.domain.signed
            )
            
            intersected = result.domain.intersect(new_result_domain)
            if intersected.is_empty():
                return PropagationResult(PropagationStatus.CONFLICT, changed)
            
            if intersected != result.domain:
                result.domain = intersected
                changed.add(self.result_var)
        
        # Backward propagation: result -> input
        # Filter input values that don't produce valid clog2 results
        valid_results = set(result.domain.values())
        valid_inputs = []
        
        for value in input_domain.values():
            clog2_val = self._clog2(value)
            if clog2_val in valid_results:
                valid_inputs.append(value)
        
        if not valid_inputs:
            return PropagationResult(PropagationStatus.CONFLICT, changed)
        
        # Convert to intervals
        if valid_inputs:
            new_input_intervals = []
            valid_inputs.sort()
            
            start = valid_inputs[0]
            end = valid_inputs[0]
            
            for val in valid_inputs[1:]:
                if val == end + 1:
                    end = val
                else:
                    new_input_intervals.append((start, end))
                    start = val
                    end = val
            new_input_intervals.append((start, end))
            
            new_input_domain = IntDomain(
                new_input_intervals,
                width=input_domain.width,
                signed=input_domain.signed
            )
            
            intersected = input_domain.intersect(new_input_domain)
            if intersected.is_empty():
                return PropagationResult(PropagationStatus.CONFLICT, changed)
            
            if intersected != input_domain:
                input_var.domain = intersected
                changed.add(self.input_var)
        
        status = PropagationStatus.FIXED_POINT if not changed else PropagationStatus.CONSISTENT
        return PropagationResult(status, changed)
    
    def affected_variables(self) -> Set[str]:
        """Return variables affected by this propagator"""
        return {self.result_var, self.input_var}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if assignment satisfies the constraint"""
        if self.result_var not in assignment or self.input_var not in assignment:
            return False
        
        result_val = assignment[self.result_var]
        input_val = assignment[self.input_var]
        
        expected_clog2 = self._clog2(input_val)
        return result_val == expected_clog2
    
    def __repr__(self) -> str:
        return f"Clog2Propagator({self.result_var} = $clog2({self.input_var}))"


class UserFunctionPropagator(Propagator):
    """
    Propagator for user-defined pure functions.
    
    Supports user-defined functions that:
    - Are side-effect free
    - Have deterministic results
    - Can be evaluated given input values
    
    This is a generic propagator that takes a callable function.
    """
    
    def __init__(self, result_var: str, input_vars: list[str], 
                 func: callable, func_name: str = "user_function"):
        """
        Args:
            result_var: Variable to store function result
            input_vars: List of input variable names
            func: Pure function to evaluate (takes *args, returns int)
            func_name: Name of the function for debugging
        """
        self.result_var = result_var
        self.input_vars = input_vars
        self.func = func
        self.func_name = func_name
    
    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        """Propagate user function constraint"""
        result = variables[self.result_var]
        inputs = [variables[var] for var in self.input_vars]
        
        changed = set()
        
        # Forward propagation: try to compute possible results
        # This requires enumerating input combinations, which can be expensive
        # For now, we only propagate if all inputs are assigned
        
        all_assigned = all(inp.is_assigned() for inp in inputs)
        
        if all_assigned:
            # Evaluate the function
            input_values = [inp.current_value for inp in inputs]
            try:
                func_result = self.func(*input_values)
                
                # Constrain result to this value
                new_domain = IntDomain(
                    [(func_result, func_result)],
                    width=result.domain.width,
                    signed=result.domain.signed
                )
                
                intersected = result.domain.intersect(new_domain)
                if intersected.is_empty():
                    return PropagationResult(PropagationStatus.CONFLICT, changed)
                
                if intersected != result.domain:
                    result.domain = intersected
                    changed.add(self.result_var)
            except Exception:
                # Function evaluation failed - this is a conflict
                return PropagationResult(PropagationStatus.CONFLICT, changed)
        
        # Note: Backward propagation (result -> inputs) is generally not
        # feasible for arbitrary functions. We'd need to enumerate all
        # possible input combinations, which is exponentially expensive.
        # This is left for future optimization if needed.
        
        status = PropagationStatus.FIXED_POINT if not changed else PropagationStatus.CONSISTENT
        return PropagationResult(status, changed)
    
    def affected_variables(self) -> Set[str]:
        """Return variables affected by this propagator"""
        return {self.result_var, *self.input_vars}
    
    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        """Check if assignment satisfies the constraint"""
        if self.result_var not in assignment:
            return False
        
        for var in self.input_vars:
            if var not in assignment:
                return False
        
        result_val = assignment[self.result_var]
        input_vals = [assignment[var] for var in self.input_vars]
        
        try:
            expected_result = self.func(*input_vals)
            return result_val == expected_result
        except Exception:
            return False
    
    def __repr__(self) -> str:
        inputs_str = ", ".join(self.input_vars)
        return f"UserFunctionPropagator({self.result_var} = {self.func_name}({inputs_str}))"
