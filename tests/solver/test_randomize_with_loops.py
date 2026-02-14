"""Tests for randomize_with + iterative constraints integration"""

from dataclasses import dataclass
from typing import List
import pytest
from zuspec.dataclasses import rand, randomize_with, constraint


def test_randomize_with_simple_loop():
    """Test basic for loop in randomize_with"""
    @dataclass
    class Simple:
        arr: List[int] = rand(size=5, domain=(0, 100))
    
    obj = Simple()
    
    with randomize_with(obj):
        for i in range(5):
            assert obj.arr[i] < 50
    
    # All elements should be < 50
    for val in obj.arr:
        assert val < 50


def test_randomize_with_partial_loop():
    """Test loop over partial array"""
    @dataclass
    class Partial:
        arr: List[int] = rand(size=10, domain=(0, 100))
    
    obj = Partial()
    
    with randomize_with(obj):
        # Only constrain first 5 elements
        for i in range(5):
            assert obj.arr[i] < 30
    
    # First 5 should be < 30
    for i in range(5):
        assert obj.arr[i] < 30
    # Rest can be anything in domain


def test_randomize_with_loop_and_scalar():
    """Test mixing loop and scalar constraints"""
    @dataclass
    class Mixed:
        value: int = rand(domain=(10, 50))
        arr: List[int] = rand(size=5, domain=(0, 100))
    
    obj = Mixed()
    
    with randomize_with(obj):
        assert obj.value > 20
        for i in range(5):
            assert obj.arr[i] >= obj.value
    
    assert obj.value > 20
    for val in obj.arr:
        assert val >= obj.value


def test_randomize_with_nested_loops():
    """Test nested loops in randomize_with"""
    @dataclass
    class Matrix:
        matrix: List[int] = rand(size=9, domain=(0, 100))  # 3x3
    
    obj = Matrix()
    
    with randomize_with(obj):
        for i in range(3):
            for j in range(3):
                assert obj.matrix[i * 3 + j] < 60
    
    for val in obj.matrix:
        assert val < 60


def test_randomize_with_ascending():
    """Test creating ascending order via randomize_with"""
    @dataclass
    class Ordered:
        arr: List[int] = rand(size=6, domain=(0, 100))
    
    obj = Ordered()
    
    with randomize_with(obj):
        for i in range(5):
            assert obj.arr[i] < obj.arr[i + 1]
    
    # Check strictly ascending
    for i in range(5):
        assert obj.arr[i] < obj.arr[i + 1]


def test_randomize_with_len():
    """Test using len() in randomize_with loop"""
    @dataclass
    class Dynamic:
        buffer: List[int] = rand(size=8, domain=(0, 255))
    
    obj = Dynamic()
    
    with randomize_with(obj):
        for i in range(len(obj.buffer)):
            assert obj.buffer[i] < 128
    
    assert len(obj.buffer) == 8
    for val in obj.buffer:
        assert val < 128


def test_randomize_with_variable_bound():
    """Test variable-bounded loop in randomize_with"""
    @dataclass
    class VarBound:
        count: int = rand(domain=(3, 7))
        arr: List[int] = rand(size=10, domain=(0, 100))
    
    obj = VarBound()
    
    with randomize_with(obj):
        assert obj.count >= 3
        for i in range(obj.count):
            assert obj.arr[i] < 30
    
    assert obj.count >= 3
    for i in range(obj.count):
        assert obj.arr[i] < 30


def test_randomize_with_multiple_loops():
    """Test multiple separate loops in randomize_with"""
    @dataclass
    class MultiLoop:
        arr1: List[int] = rand(size=4, domain=(0, 100))
        arr2: List[int] = rand(size=4, domain=(0, 100))
    
    obj = MultiLoop()
    
    with randomize_with(obj):
        for i in range(4):
            assert obj.arr1[i] < 40
        
        for i in range(4):
            assert obj.arr2[i] >= 60
    
    for val in obj.arr1:
        assert val < 40
    for val in obj.arr2:
        assert val >= 60


def test_randomize_with_computed_index():
    """Test computed indices in randomize_with loop"""
    @dataclass
    class Computed:
        arr: List[int] = rand(size=8, domain=(0, 100))
    
    obj = Computed()
    
    with randomize_with(obj):
        for i in range(4):
            # First half small
            assert obj.arr[i] < 30
            # Second half large
            assert obj.arr[i + 4] >= 70
    
    for i in range(4):
        assert obj.arr[i] < 30
        assert obj.arr[i + 4] >= 70


def test_randomize_with_loop_reproducible():
    """Test loops in randomize_with are reproducible"""
    @dataclass
    class Repro:
        arr: List[int] = rand(size=6, domain=(0, 100))
    
    obj1 = Repro()
    with randomize_with(obj1, seed=12345):
        for i in range(6):
            assert obj1.arr[i] < 70
    
    obj2 = Repro()
    with randomize_with(obj2, seed=12345):
        for i in range(6):
            assert obj2.arr[i] < 70
    
    assert obj1.arr == obj2.arr


def test_randomize_with_class_constraint_and_loop():
    """Test combining class @constraint with randomize_with loop"""
    @dataclass
    class Combined:
        value: int = rand(domain=(10, 50))
        arr: List[int] = rand(size=5, domain=(0, 100))
        
        @constraint
        def base_constraint(self):
            assert self.value > 15
    
    obj = Combined()
    
    # Add additional constraints with randomize_with
    with randomize_with(obj):
        assert obj.value < 40
        for i in range(5):
            assert obj.arr[i] >= obj.value
    
    # Both constraints should apply
    assert 15 < obj.value < 40
    for val in obj.arr:
        assert val >= obj.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
