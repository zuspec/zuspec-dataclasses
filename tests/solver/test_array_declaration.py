"""Tests for array field declaration and randomization"""

import pytest
from dataclasses import dataclass
from typing import List

# Import from local package
from zuspec.dataclasses import rand, randc, randomize, constraint, RandomizationError


def test_array_fixed_size_basic():
    """Test basic fixed-size array declaration"""
    @dataclass
    class ArrayModel:
        arr: List[int] = rand(size=4, domain=(0, 10))
    
    obj = ArrayModel()
    randomize(obj)
    
    assert hasattr(obj, 'arr')
    assert isinstance(obj.arr, list)
    assert len(obj.arr) == 4
    assert all(isinstance(x, int) for x in obj.arr)
    assert all(0 <= x <= 10 for x in obj.arr)


def test_array_single_element():
    """Test array with size=1"""
    @dataclass
    class SingleArray:
        val: List[int] = rand(size=1, domain=(5, 5))
    
    obj = SingleArray()
    randomize(obj)
    
    assert len(obj.val) == 1
    assert obj.val[0] == 5


def test_array_large():
    """Test larger array (100 elements)"""
    @dataclass
    class LargeArray:
        big: List[int] = rand(size=100, domain=(0, 1))
    
    obj = LargeArray()
    randomize(obj)
    
    assert len(obj.big) == 100
    assert all(x in [0, 1] for x in obj.big)


def test_array_with_scalar_fields():
    """Test array mixed with scalar fields"""
    @dataclass
    class Mixed:
        x: int = rand(domain=(1, 10))
        arr: List[int] = rand(size=3, domain=(20, 30))
        y: int = rand(domain=(1, 10))
    
    obj = Mixed()
    randomize(obj)
    
    assert 1 <= obj.x <= 10
    assert len(obj.arr) == 3
    assert all(20 <= v <= 30 for v in obj.arr)
    assert 1 <= obj.y <= 10


def test_multiple_arrays():
    """Test multiple arrays in same model"""
    @dataclass
    class MultiArray:
        arr1: List[int] = rand(size=2, domain=(0, 10))
        arr2: List[int] = rand(size=3, domain=(100, 200))
    
    obj = MultiArray()
    randomize(obj)
    
    assert len(obj.arr1) == 2
    assert all(0 <= x <= 10 for x in obj.arr1)
    assert len(obj.arr2) == 3
    assert all(100 <= x <= 200 for x in obj.arr2)


def test_array_domain_enforcement():
    """Test that all array elements respect domain constraints"""
    @dataclass
    class DomainTest:
        data: List[int] = rand(size=10, domain=(50, 60))
    
    obj = DomainTest()
    randomize(obj)
    
    assert len(obj.data) == 10
    for i, val in enumerate(obj.data):
        assert 50 <= val <= 60, f"Element {i} = {val} outside domain [50, 60]"


def test_array_invalid_size_zero():
    """Test that size=0 raises error"""
    with pytest.raises(ValueError, match="size must be positive"):
        @dataclass
        class InvalidArray:
            arr: List[int] = rand(size=0, domain=(0, 10))


def test_array_invalid_size_negative():
    """Test that negative size raises error"""
    with pytest.raises(ValueError, match="size must be positive"):
        @dataclass
        class InvalidArray:
            arr: List[int] = rand(size=-1, domain=(0, 10))


def test_array_invalid_size_type():
    """Test that non-integer size raises error"""
    with pytest.raises(TypeError, match="size must be an integer"):
        @dataclass
        class InvalidArray:
            arr: List[int] = rand(size="10", domain=(0, 10))


def test_array_without_size_errors():
    """Test that List[T] without size parameter fails in Phase 1A"""
    with pytest.raises(Exception, match="must specify size parameter"):
        # This should fail during dataclass IR build or randomization
        @dataclass
        class VariableSize:
            buffer: List[int] = rand(domain=(0, 255))
        
        obj = VariableSize()
        randomize(obj)


def test_array_reproducible_with_seed():
    """Test that array randomization is reproducible with seed"""
    @dataclass
    class SeededArray:
        data: List[int] = rand(size=5, domain=(0, 100))
    
    obj1 = SeededArray()
    randomize(obj1, seed=42)
    
    obj2 = SeededArray()
    randomize(obj2, seed=42)
    
    assert obj1.data == obj2.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
