"""Tests for array indexing in constraints (Phase 2)"""

import pytest
from dataclasses import dataclass
from typing import List

from zuspec.dataclasses import rand, randomize, constraint, RandomizationError


def test_array_index_single_element():
    """Test constraint on single array element"""
    @dataclass
    class ArrayIndex:
        arr: List[int] = rand(size=4, domain=(0, 100))
        
        @constraint
        def first_element(self):
            assert self.arr[0] == 42
    
    obj = ArrayIndex()
    randomize(obj)
    
    assert obj.arr[0] == 42
    assert 0 <= obj.arr[1] <= 100
    assert 0 <= obj.arr[2] <= 100
    assert 0 <= obj.arr[3] <= 100


def test_array_index_last_element():
    """Test constraint on last array element"""
    @dataclass
    class LastElement:
        arr: List[int] = rand(size=5, domain=(0, 50))
        
        @constraint
        def last(self):
            assert self.arr[4] == 10
    
    obj = LastElement()
    randomize(obj)
    
    assert obj.arr[4] == 10
    for i in range(4):
        assert 0 <= obj.arr[i] <= 50


def test_array_index_multiple():
    """Test constraints on multiple elements"""
    @dataclass
    class MultiIndex:
        arr: List[int] = rand(size=3, domain=(0, 100))
        
        @constraint
        def ascending(self):
            assert self.arr[0] < self.arr[1]
            assert self.arr[1] < self.arr[2]
    
    obj = MultiIndex()
    randomize(obj)
    
    assert obj.arr[0] < obj.arr[1] < obj.arr[2]


def test_array_index_with_scalar():
    """Test array element compared to scalar"""
    @dataclass
    class WithScalar:
        count: int = rand(domain=(5, 10))
        values: List[int] = rand(size=10, domain=(0, 20))
        
        @constraint
        def match(self):
            assert self.values[0] == self.count
    
    obj = WithScalar()
    randomize(obj)
    
    assert obj.values[0] == obj.count
    assert 5 <= obj.count <= 10


def test_array_index_arithmetic():
    """Test array elements in arithmetic expressions"""
    @dataclass
    class Arithmetic:
        arr: List[int] = rand(size=3, domain=(0, 50))
        
        @constraint
        def sum_constraint(self):
            # Make sure the constraint is satisfiable
            assert self.arr[0] + self.arr[1] <= 50
            assert self.arr[2] >= self.arr[0]
    
    obj = Arithmetic()
    randomize(obj)
    
    assert obj.arr[0] + obj.arr[1] <= 50
    assert obj.arr[2] >= obj.arr[0]


def test_array_index_all_elements():
    """Test constraining all array elements"""
    @dataclass
    class AllConstrained:
        arr: List[int] = rand(size=3, domain=(0, 100))
        
        @constraint
        def all_even(self):
            assert self.arr[0] % 2 == 0
            assert self.arr[1] % 2 == 0
            assert self.arr[2] % 2 == 0
    
    obj = AllConstrained()
    randomize(obj)
    
    assert all(x % 2 == 0 for x in obj.arr)


def test_array_index_mixed_constraints():
    """Test array and scalar constraints together"""
    @dataclass
    class Mixed:
        x: int = rand(domain=(10, 20))
        arr: List[int] = rand(size=5, domain=(0, 100))
        y: int = rand(domain=(50, 60))
        
        @constraint
        def relations(self):
            assert self.arr[0] > self.x
            assert self.arr[4] < self.y
    
    obj = Mixed()
    randomize(obj)
    
    assert obj.arr[0] > obj.x
    assert obj.arr[4] < obj.y


def test_array_index_comparison_chain():
    """Test multiple comparisons with array elements"""
    @dataclass
    class CompareChain:
        arr: List[int] = rand(size=4, domain=(0, 100))
        
        @constraint
        def strictly_increasing(self):
            # Note: Comparison chains may not be fully supported, so split them
            assert self.arr[0] < self.arr[1]
            assert self.arr[1] < self.arr[2]
            assert self.arr[2] < self.arr[3]
    
    obj = CompareChain()
    randomize(obj)
    
    assert obj.arr[0] < obj.arr[1] < obj.arr[2] < obj.arr[3]


def test_array_index_out_of_bounds():
    """Test that out-of-bounds index raises error"""
    with pytest.raises(Exception, match="out of bounds"):
        @dataclass
        class OutOfBounds:
            arr: List[int] = rand(size=4, domain=(0, 10))
            
            @constraint
            def bad_index(self):
                assert self.arr[10] == 5  # Index 10 >= size 4
        
        obj = OutOfBounds()
        randomize(obj)


def test_array_index_negative():
    """Test that negative indices raise error"""
    with pytest.raises(Exception, match="Negative array indices not supported"):
        @dataclass
        class NegativeIndex:
            arr: List[int] = rand(size=4, domain=(0, 10))
            
            @constraint
            def bad_index(self):
                assert self.arr[-1] == 5  # Negative index (seen as UnaryOp by parser)
        
        obj = NegativeIndex()
        randomize(obj)


def test_array_index_boundary():
    """Test indexing at array boundaries"""
    @dataclass
    class Boundary:
        arr: List[int] = rand(size=5, domain=(0, 10))
        
        @constraint
        def bounds(self):
            assert self.arr[0] >= 0   # First element
            assert self.arr[4] <= 10  # Last element (size-1)
    
    obj = Boundary()
    randomize(obj)
    
    assert 0 <= obj.arr[0] <= 10
    assert 0 <= obj.arr[4] <= 10


def test_array_index_multiple_arrays():
    """Test indexing multiple arrays"""
    @dataclass
    class MultiArray:
        arr1: List[int] = rand(size=3, domain=(0, 10))
        arr2: List[int] = rand(size=3, domain=(20, 30))
        
        @constraint
        def cross_constraint(self):
            assert self.arr1[0] + self.arr2[0] == 25
    
    obj = MultiArray()
    randomize(obj)
    
    assert obj.arr1[0] + obj.arr2[0] == 25


def test_array_index_complex_expression():
    """Test array elements in complex expressions"""
    @dataclass
    class ComplexExpr:
        arr: List[int] = rand(size=4, domain=(1, 20))
        
        @constraint
        def complex(self):
            # Simplified constraints that are satisfiable
            assert self.arr[0] * 2 < 40
            assert self.arr[1] > 0
            assert self.arr[2] < 20
            assert self.arr[3] >= self.arr[0]
    
    obj = ComplexExpr()
    randomize(obj)
    
    assert obj.arr[0] * 2 < 40
    assert obj.arr[1] > 0
    assert obj.arr[2] < 20
    assert obj.arr[3] >= obj.arr[0]


def test_array_index_different_domains():
    """Test arrays with different element domains"""
    @dataclass
    class DiffDomains:
        small: List[int] = rand(size=2, domain=(0, 10))
        large: List[int] = rand(size=2, domain=(100, 200))
        
        @constraint
        def relation(self):
            assert self.small[0] < 5
            assert self.large[1] > 150
    
    obj = DiffDomains()
    randomize(obj)
    
    assert obj.small[0] < 5
    assert obj.large[1] > 150


def test_array_index_reproducible():
    """Test that array indexing constraints are reproducible with seed"""
    @dataclass
    class Reproducible:
        arr: List[int] = rand(size=4, domain=(0, 100))
        
        @constraint
        def pattern(self):
            assert self.arr[0] < self.arr[3]
    
    obj1 = Reproducible()
    randomize(obj1, seed=777)
    
    obj2 = Reproducible()
    randomize(obj2, seed=777)
    
    assert obj1.arr == obj2.arr
    assert obj1.arr[0] < obj1.arr[3]


def test_array_index_single_element_array():
    """Test indexing into single-element array"""
    @dataclass
    class SingleElem:
        arr: List[int] = rand(size=1, domain=(42, 42))
        
        @constraint
        def only_elem(self):
            assert self.arr[0] == 42
    
    obj = SingleElem()
    randomize(obj)
    
    assert obj.arr[0] == 42


def test_array_index_with_modulo():
    """Test array constraints with modulo operations"""
    @dataclass
    class ModuloTest:
        arr: List[int] = rand(size=5, domain=(0, 100))
        
        @constraint
        def mod_constraints(self):
            assert self.arr[0] % 10 == 5
            assert self.arr[2] % 3 == 0
    
    obj = ModuloTest()
    randomize(obj)
    
    assert obj.arr[0] % 10 == 5
    assert obj.arr[2] % 3 == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
