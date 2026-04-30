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


class SextPropagator(Propagator):
    """Propagator for zdc.sext(value, bits) — sign-extend from bits-wide source.

    Forward:  given value_var domain and bits constant, constrain result_var.
    Backward: given result_var domain, constrain value_var.

    bits is always a compile-time constant per the synthesizable-subset rules.
    """

    def __init__(self, result_var: str, value_var: str, bits: int):
        self.result_var = result_var
        self.value_var = value_var
        self.bits = bits
        self._mask = (1 << bits) - 1
        self._sign_bit = 1 << (bits - 1)

    @staticmethod
    def _sext(val: int, bits: int) -> int:
        mask = (1 << bits) - 1
        val = val & mask
        if val & (1 << (bits - 1)):
            return val - (1 << bits)
        return val

    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        result = variables[self.result_var]
        value_var = variables[self.value_var]
        changed = set()

        input_domain = value_var.domain
        if not isinstance(input_domain, IntDomain):
            return PropagationResult(PropagationStatus.FIXED_POINT, changed)

        # Forward: enumerate input values and compute sext results
        possible_results = set()
        for val in input_domain.values():
            possible_results.add(self._sext(val, self.bits))

        if possible_results:
            sorted_r = sorted(possible_results)
            intervals = []
            start = end = sorted_r[0]
            for v in sorted_r[1:]:
                if v == end + 1:
                    end = v
                else:
                    intervals.append((start, end))
                    start = end = v
            intervals.append((start, end))

            new_domain = IntDomain(intervals, width=result.domain.width,
                                   signed=result.domain.signed)
            intersected = result.domain.intersect(new_domain)
            if intersected.is_empty():
                return PropagationResult(PropagationStatus.CONFLICT, changed)
            if intersected != result.domain:
                result.domain = intersected
                changed.add(result)

        # Backward: filter input values whose sext is not in result domain
        valid_results = set(result.domain.values())
        valid_inputs = [v for v in input_domain.values()
                        if self._sext(v, self.bits) in valid_results]
        if not valid_inputs:
            return PropagationResult(PropagationStatus.CONFLICT, changed)

        sorted_i = sorted(valid_inputs)
        intervals = []
        start = end = sorted_i[0]
        for v in sorted_i[1:]:
            if v == end + 1:
                end = v
            else:
                intervals.append((start, end))
                start = end = v
        intervals.append((start, end))

        new_input = IntDomain(intervals, width=input_domain.width,
                              signed=input_domain.signed)
        intersected = input_domain.intersect(new_input)
        if intersected.is_empty():
            return PropagationResult(PropagationStatus.CONFLICT, changed)
        if intersected != input_domain:
            value_var.domain = intersected
            changed.add(value_var)

        status = PropagationStatus.FIXED_POINT if not changed else PropagationStatus.CONSISTENT
        return PropagationResult(status, changed)

    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.value_var}

    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if self.result_var not in assignment or self.value_var not in assignment:
            return False
        return assignment[self.result_var] == self._sext(assignment[self.value_var], self.bits)

    def __repr__(self) -> str:
        return f"SextPropagator({self.result_var} = sext({self.value_var}, {self.bits}))"


class CbitPropagator(Propagator):
    """Propagator for zdc.cbit(expr) — reify a boolean to 0/1.

    result_var ∈ {0, 1} and equals 1 iff inner_var != 0.
    Useful when the inner expression is already a VariableRef (e.g. a comparison
    result stored in a temp variable).
    """

    def __init__(self, result_var: str, inner_var: str):
        self.result_var = result_var
        self.inner_var = inner_var

    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        result = variables[self.result_var]
        inner = variables[self.inner_var]
        changed = set()

        inner_domain = inner.domain
        if not isinstance(inner_domain, IntDomain):
            return PropagationResult(PropagationStatus.FIXED_POINT, changed)

        # Forward: narrow result domain based on what inner can produce
        possible = set()
        for v in inner_domain.values():
            possible.add(1 if v else 0)

        sorted_p = sorted(possible)
        intervals = [(v, v) for v in sorted_p]
        new_domain = IntDomain(intervals, width=result.domain.width,
                               signed=result.domain.signed)
        intersected = result.domain.intersect(new_domain)
        if intersected.is_empty():
            return PropagationResult(PropagationStatus.CONFLICT, changed)
        if intersected != result.domain:
            result.domain = intersected
            changed.add(result)

        # Backward: narrow inner domain based on result
        if result.domain.is_singleton():
            result_val = result.domain.min_val
            if result_val == 1:
                # result=1 → inner must be non-zero; exclude 0 from inner domain
                if inner_domain.min_val == 0:
                    new_inner = IntDomain([(1, inner_domain.max_val)],
                                         width=inner_domain.width,
                                         signed=inner_domain.signed)
                    if new_inner.is_empty():
                        return PropagationResult(PropagationStatus.CONFLICT, changed)
                    inner.domain = new_inner
                    changed.add(inner)
            elif result_val == 0:
                # result=0 → inner must be zero
                new_inner = IntDomain([(0, 0)], width=inner_domain.width,
                                      signed=inner_domain.signed)
                intersected_inner = inner_domain.intersect(new_inner)
                if intersected_inner.is_empty():
                    return PropagationResult(PropagationStatus.CONFLICT, changed)
                if intersected_inner != inner_domain:
                    inner.domain = intersected_inner
                    changed.add(inner)

        status = PropagationStatus.FIXED_POINT if not changed else PropagationStatus.CONSISTENT
        return PropagationResult(status, changed)

    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.inner_var}

    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if self.result_var not in assignment or self.inner_var not in assignment:
            return False
        expected = 1 if assignment[self.inner_var] else 0
        return assignment[self.result_var] == expected

    def __repr__(self) -> str:
        return f"CbitPropagator({self.result_var} = cbit({self.inner_var}))"


class SignedViewPropagator(Propagator):
    """Propagator for zdc.signed(val) — treat a value as signed 32-bit.

    This is a transparent wrapper: result_var == signed_view(inner_var).
    Forward propagation maps the unsigned domain to signed integers;
    backward restricts the inner domain accordingly.
    """

    def __init__(self, result_var: str, inner_var: str, width: int = 32):
        self.result_var = result_var
        self.inner_var = inner_var
        self.width = width
        self._mask = (1 << width) - 1
        self._sign_bit = 1 << (width - 1)
        self._mod = 1 << width

    def _to_signed(self, val: int) -> int:
        val = val & self._mask
        if val >= self._sign_bit:
            return val - self._mod
        return val

    def propagate(self, variables: Dict[str, Variable]) -> PropagationResult:
        result = variables[self.result_var]
        inner = variables[self.inner_var]
        changed = set()

        inner_domain = inner.domain
        if not isinstance(inner_domain, IntDomain):
            return PropagationResult(PropagationStatus.FIXED_POINT, changed)

        possible = set()
        for v in inner_domain.values():
            possible.add(self._to_signed(v))

        if possible:
            sorted_p = sorted(possible)
            intervals = []
            start = end = sorted_p[0]
            for v in sorted_p[1:]:
                if v == end + 1:
                    end = v
                else:
                    intervals.append((start, end))
                    start = end = v
            intervals.append((start, end))

            new_domain = IntDomain(intervals, width=result.domain.width,
                                   signed=True)
            intersected = result.domain.intersect(new_domain)
            if intersected.is_empty():
                return PropagationResult(PropagationStatus.CONFLICT, changed)
            if intersected != result.domain:
                result.domain = intersected
                changed.add(result)

        status = PropagationStatus.FIXED_POINT if not changed else PropagationStatus.CONSISTENT
        return PropagationResult(status, changed)

    def affected_variables(self) -> Set[str]:
        return {self.result_var, self.inner_var}

    def is_satisfied(self, assignment: Dict[str, int]) -> bool:
        if self.result_var not in assignment or self.inner_var not in assignment:
            return False
        return assignment[self.result_var] == self._to_signed(assignment[self.inner_var])

    def __repr__(self) -> str:
        return f"SignedViewPropagator({self.result_var} = signed({self.inner_var}))"
