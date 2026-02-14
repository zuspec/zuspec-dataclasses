"""Tests for Phase 3: Iterative Constraints (for loops in constraints)"""

from dataclasses import dataclass
from typing import List
import pytest
from zuspec.dataclasses import rand, randc, randomize, constraint


# ==============================================================================
# Basic Fixed-Range Loops
# ==============================================================================

def test_for_range_fixed():
    """Test basic for loop with fixed range"""
    @dataclass
    class BasicLoop:
        arr: List[int] = rand(size=5, domain=(0, 100))
        
        @constraint
        def all_small(self):
            for i in range(5):
                assert self.arr[i] < 50
    
    obj = BasicLoop()
    randomize(obj)
    
    # All elements should be < 50
    for val in obj.arr:
        assert val < 50


def test_for_range_partial():
    """Test loop over partial range"""
    @dataclass
    class PartialLoop:
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def first_five_small(self):
            for i in range(5):
                assert self.arr[i] < 30
    
    obj = PartialLoop()
    randomize(obj)
    
    # First 5 elements should be < 30
    for i in range(5):
        assert obj.arr[i] < 30
    # Rest can be anything in domain


def test_for_range_with_start():
    """Test range(start, stop)"""
    @dataclass
    class RangeStartStop:
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def middle_elements(self):
            for i in range(2, 8):
                assert self.arr[i] >= 50
    
    obj = RangeStartStop()
    randomize(obj)
    
    # Elements 2-7 should be >= 50
    for i in range(2, 8):
        assert obj.arr[i] >= 50


def test_for_range_with_step():
    """Test range(start, stop, step)"""
    @dataclass
    class RangeWithStep:
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def even_indices(self):
            for i in range(0, 10, 2):
                assert self.arr[i] < 30
    
    obj = RangeWithStep()
    randomize(obj)
    
    # Even indices should be < 30
    for i in range(0, 10, 2):
        assert obj.arr[i] < 30


def test_for_range_len():
    """Test range(len(array))"""
    @dataclass
    class LenRange:
        buffer: List[int] = rand(size=16, domain=(0, 255))
        
        @constraint
        def all_values(self):
            for i in range(len(self.buffer)):
                assert self.buffer[i] < 128
    
    obj = LenRange()
    randomize(obj)
    
    assert len(obj.buffer) == 16
    for val in obj.buffer:
        assert val < 128


# ==============================================================================
# Multiple Constraints in Loop Body
# ==============================================================================

def test_multiple_constraints_in_loop():
    """Test loop body with multiple assertions"""
    @dataclass
    class MultipleAsserts:
        arr: List[int] = rand(size=5, domain=(10, 90))
        
        @constraint
        def range_constraints(self):
            for i in range(5):
                assert self.arr[i] >= 20
                assert self.arr[i] <= 80
                assert self.arr[i] % 2 == 0  # Even
    
    obj = MultipleAsserts()
    randomize(obj)
    
    for val in obj.arr:
        assert 20 <= val <= 80
        assert val % 2 == 0


# ==============================================================================
# Loops with Non-Loop Constraints
# ==============================================================================

def test_loop_with_scalar_constraints():
    """Test mixing loop and scalar constraints"""
    @dataclass
    class MixedConstraints:
        count: int = rand(domain=(5, 10))
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def mixed(self):
            assert self.count >= 5
            for i in range(5):
                assert self.arr[i] < 50
            assert self.arr[0] < self.count
    
    obj = MixedConstraints()
    randomize(obj)
    
    assert obj.count >= 5
    for i in range(5):
        assert obj.arr[i] < 50
    assert obj.arr[0] < obj.count


def test_multiple_loops():
    """Test multiple separate for loops"""
    @dataclass
    class MultipleLoops:
        arr1: List[int] = rand(size=4, domain=(0, 100))
        arr2: List[int] = rand(size=4, domain=(0, 100))
        
        @constraint
        def two_loops(self):
            for i in range(4):
                assert self.arr1[i] < 50
            for i in range(4):
                assert self.arr2[i] >= 50
    
    obj = MultipleLoops()
    randomize(obj)
    
    for val in obj.arr1:
        assert val < 50
    for val in obj.arr2:
        assert val >= 50


# ==============================================================================
# Common Patterns
# ==============================================================================

def test_loop_all_equal():
    """Test setting all elements to same value"""
    @dataclass
    class AllEqual:
        arr: List[int] = rand(size=5, domain=(0, 100))
        value: int = rand(domain=(10, 20))
        
        @constraint
        def all_same(self):
            for i in range(5):
                assert self.arr[i] == self.value
    
    obj = AllEqual()
    randomize(obj)
    
    # All elements should equal the value
    for val in obj.arr:
        assert val == obj.value
    assert 10 <= obj.value <= 20


def test_loop_ascending():
    """Test enforcing ascending order"""
    @dataclass
    class Ascending:
        arr: List[int] = rand(size=5, domain=(0, 100))
        
        @constraint
        def ordered(self):
            for i in range(4):  # Note: 4 not 5
                assert self.arr[i] < self.arr[i + 1]
    
    obj = Ascending()
    randomize(obj)
    
    # Check strictly ascending
    for i in range(4):
        assert obj.arr[i] < obj.arr[i + 1]


def test_loop_unique():
    """Test enforcing all different values (simplified)"""
    @dataclass
    class Unique:
        arr: List[int] = rand(size=3, domain=(0, 100))
        
        @constraint
        def all_different(self):
            # Manually unroll uniqueness constraints
            assert self.arr[0] != self.arr[1]
            assert self.arr[0] != self.arr[2]
            assert self.arr[1] != self.arr[2]
    
    obj = Unique()
    randomize(obj)
    
    # Check all unique
    assert len(set(obj.arr)) == 3


# ==============================================================================
# Nested Loops
# ==============================================================================

def test_nested_loops_simple():
    """Test simple nested loops"""
    @dataclass
    class NestedSimple:
        matrix: List[int] = rand(size=9, domain=(0, 100))  # 3x3 flattened
        
        @constraint
        def all_elements(self):
            # Constrain all elements to be in a specific range
            for i in range(3):
                for j in range(3):
                    assert self.matrix[i * 3 + j] < 80
    
    obj = NestedSimple()
    randomize(obj)
    
    # Check all elements
    for val in obj.matrix:
        assert val < 80


def test_nested_loops_all_pairs():
    """Test nested loops covering all pairs"""
    @dataclass
    class AllPairs:
        arr: List[int] = rand(size=4, domain=(10, 40))
        
        @constraint
        def all_pairs_sum(self):
            # All pairs sum constraints (without if)
            for i in range(4):
                for j in range(4):
                    assert self.arr[i] + self.arr[j] < 80
    
    obj = AllPairs()
    randomize(obj)
    
    # Check all pairs
    for i in range(4):
        for j in range(4):
            assert obj.arr[i] + obj.arr[j] < 80


# ==============================================================================
# Variable-Bounded Loops
# ==============================================================================

def test_variable_bound_basic():
    """Test loop bounded by random variable"""
    @dataclass
    class VarBound:
        count: int = rand(domain=(3, 8))
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def first_count_small(self):
            for i in range(self.count):
                assert self.arr[i] < 30
    
    obj = VarBound()
    randomize(obj)
    
    # First 'count' elements should be < 30
    for i in range(obj.count):
        assert obj.arr[i] < 30
    # Rest can be anything


def test_variable_bound_with_scalar():
    """Test variable-bounded loop with scalar constraint"""
    @dataclass
    class VarBoundScalar:
        count: int = rand(domain=(2, 6))
        arr: List[int] = rand(size=8, domain=(0, 100))
        value: int = rand(domain=(10, 20))
        
        @constraint
        def constraints(self):
            assert self.count >= 2
            for i in range(self.count):
                assert self.arr[i] >= self.value
    
    obj = VarBoundScalar()
    randomize(obj)
    
    assert obj.count >= 2
    for i in range(obj.count):
        assert obj.arr[i] >= obj.value


def test_variable_bound_multiple_loops():
    """Test multiple variable-bounded loops"""
    @dataclass
    class MultiVarBound:
        count1: int = rand(domain=(2, 5))
        count2: int = rand(domain=(3, 6))
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def two_regions(self):
            for i in range(self.count1):
                assert self.arr[i] < 30
            for i in range(self.count2):
                assert self.arr[i] >= 20
    
    obj = MultiVarBound()
    randomize(obj)
    
    # First count1 elements: < 30
    for i in range(obj.count1):
        assert obj.arr[i] < 30
    
    # First count2 elements: >= 20  
    for i in range(obj.count2):
        assert obj.arr[i] >= 20
    
    # Overlap region: [20, 30) if count1 and count2 overlap


@pytest.mark.skip(reason="Nested variable-bounded loops create complex implications - future enhancement")
def test_variable_bound_nested():
    """Test nested variable-bounded loops"""
    @dataclass
    class NestedVarBound:
        rows: int = rand(domain=(2, 4))
        cols: int = rand(domain=(2, 4))
        matrix: List[int] = rand(size=16, domain=(0, 100))  # 4x4 max
        
        @constraint
        def submatrix_small(self):
            for i in range(self.rows):
                for j in range(self.cols):
                    # Directly compute index without local variable
                    assert self.matrix[i * 4 + j] < 50
    
    obj = NestedVarBound()
    randomize(obj)
    
    # Check submatrix
    for i in range(obj.rows):
        for j in range(obj.cols):
            idx = i * 4 + j
            assert obj.matrix[idx] < 50


# ==============================================================================
# Edge Cases
# ==============================================================================

def test_loop_empty_range():
    """Test loop with empty range"""
    @dataclass
    class EmptyLoop:
        arr: List[int] = rand(size=5, domain=(0, 100))
        value: int = rand(domain=(10, 20))
        
        @constraint
        def empty(self):
            for i in range(0):  # Empty range
                assert self.arr[i] < 0  # Never executed
            assert self.value > 10  # This should still apply
    
    obj = EmptyLoop()
    randomize(obj)
    
    assert obj.value > 10


def test_loop_single_iteration():
    """Test loop with single iteration"""
    @dataclass
    class SingleIter:
        arr: List[int] = rand(size=5, domain=(0, 100))
        
        @constraint
        def single(self):
            for i in range(1):
                assert self.arr[i] == 42
    
    obj = SingleIter()
    randomize(obj)
    
    assert obj.arr[0] == 42


def test_loop_boundary_check():
    """Test loop doesn't exceed array bounds"""
    @dataclass
    class BoundaryCheck:
        arr: List[int] = rand(size=5, domain=(0, 100))
        
        @constraint
        def exactly_size(self):
            for i in range(5):  # Exactly array size
                assert self.arr[i] >= 0
    
    obj = BoundaryCheck()
    randomize(obj)
    
    assert len(obj.arr) == 5
    for val in obj.arr:
        assert val >= 0


def test_variable_bound_at_max():
    """Test variable bound can reach maximum (array size)"""
    @dataclass
    class VarBoundMax:
        count: int = rand(domain=(5, 10))
        arr: List[int] = rand(size=10, domain=(0, 100))
        
        @constraint
        def use_all(self):
            assert self.count == 10  # Force maximum
            for i in range(self.count):
                assert self.arr[i] < 50
    
    obj = VarBoundMax()
    randomize(obj)
    
    assert obj.count == 10
    for val in obj.arr:
        assert val < 50


# ==============================================================================
# Reproducibility
# ==============================================================================

def test_loop_reproducible():
    """Test loop constraints are reproducible with seed"""
    @dataclass
    class Reproducible:
        arr: List[int] = rand(size=8, domain=(0, 100))
        
        @constraint
        def pattern(self):
            for i in range(8):
                assert self.arr[i] < 60
    
    obj1 = Reproducible()
    randomize(obj1, seed=12345)
    
    obj2 = Reproducible()
    randomize(obj2, seed=12345)
    
    assert obj1.arr == obj2.arr


# ==============================================================================
# Complex Patterns
# ==============================================================================

def test_loop_with_computed_index():
    """Test using computed indices in loop"""
    @dataclass
    class ComputedIndex:
        arr: List[int] = rand(size=8, domain=(0, 100))
        
        @constraint
        def pattern(self):
            for i in range(4):
                # First half small, second half large
                assert self.arr[i] < 40
                assert self.arr[i + 4] >= 60
    
    obj = ComputedIndex()
    randomize(obj)
    
    for i in range(4):
        assert obj.arr[i] < 40
        assert obj.arr[i + 4] >= 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
