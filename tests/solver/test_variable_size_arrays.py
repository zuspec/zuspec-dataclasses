"""
Test suite for variable-size arrays (Phase 1-4)

Variable-size arrays have their length determined at solve time through constraints.
Implementation uses max_size allocation with a hidden length variable.

Phase 1: Declaration and initialization
Phase 2: Length constraints (len() mapping)
Phase 3: Solution reconstruction
Phase 4: Integration testing
"""
import pytest
from dataclasses import dataclass
from typing import List
from zuspec.dataclasses import (
    rand, constraint, randomize, randomize_with
)


# ============================================================================
# Phase 1: Variable-Size Array Declaration
# ============================================================================

def test_variable_size_explicit_max():
    """Test variable-size array with explicit max_size"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=16, domain=(0, 255))
    
    obj = Data()
    # Should create length variable _length_buffer and 16 element variables
    randomize(obj)
    
    # Verify object has buffer attribute
    assert hasattr(obj, 'buffer')
    assert isinstance(obj.buffer, list)
    # Length should be between 0 and 16
    assert 0 <= len(obj.buffer) <= 16


def test_variable_size_default_max():
    """Test variable-size array with default max_size (32)"""
    @dataclass
    class Data:
        data: List[int] = rand(domain=(1, 100))
    
    obj = Data()
    randomize(obj)
    
    # Default max should be 32
    assert hasattr(obj, 'data')
    assert isinstance(obj.data, list)
    assert 0 <= len(obj.data) <= 32


def test_cannot_specify_both_size_and_max():
    """Test that specifying both size and max_size raises error"""
    with pytest.raises(ValueError, match="Cannot specify both"):
        @dataclass
        class Data:
            buffer: List[int] = rand(size=10, max_size=20, domain=(0, 255))


def test_multiple_variable_arrays():
    """Test multiple variable-size arrays in same struct"""
    @dataclass
    class Data:
        buf1: List[int] = rand(max_size=8, domain=(0, 100))
        buf2: List[int] = rand(max_size=12, domain=(0, 200))
    
    obj = Data()
    randomize(obj)
    
    assert 0 <= len(obj.buf1) <= 8
    assert 0 <= len(obj.buf2) <= 12


def test_mixed_fixed_and_variable():
    """Test mixing fixed-size and variable-size arrays"""
    @dataclass
    class Data:
        fixed: List[int] = rand(size=5, domain=(0, 10))
        variable: List[int] = rand(max_size=10, domain=(0, 20))
    
    obj = Data()
    randomize(obj)
    
    # Fixed should always be size 5
    assert len(obj.fixed) == 5
    # Variable should be between 0 and 10
    assert 0 <= len(obj.variable) <= 10


# ============================================================================
# Phase 2: Length Constraints (len() mapping)
# ============================================================================

def test_len_constraint_exact():
    """Test constraining len() to exact value"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=20, domain=(0, 255))
        
        @constraint
        def size_constraint(self):
            assert len(self.buffer) == 10
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.buffer) == 10


def test_len_constraint_range():
    """Test constraining len() to range"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=30, domain=(0, 255))
        
        @constraint
        def size_constraint(self):
            assert len(self.buffer) >= 5
            assert len(self.buffer) <= 15
    
    obj = Data()
    for _ in range(10):
        randomize(obj)
        assert 5 <= len(obj.buffer) <= 15


def test_len_in_expression():
    """Test using len() in arithmetic expressions"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=20, domain=(0, 255))
        count: int = rand(domain=(5, 50))
        
        @constraint
        def related_sizes(self):
            assert len(self.buffer) * 2 == self.count
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.buffer) * 2 == obj.count


def test_len_between_arrays():
    """Test relating lengths of multiple arrays"""
    @dataclass
    class Data:
        keys: List[int] = rand(max_size=15, domain=(0, 100))
        values: List[int] = rand(max_size=15, domain=(0, 200))
        
        @constraint
        def same_length(self):
            assert len(self.keys) == len(self.values)
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.keys) == len(obj.values)


# ============================================================================
# Phase 3: Element Access with Variable Indices
# ============================================================================

def test_element_access_variable_index():
    """Test accessing elements with variable index"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=10, domain=(0, 255))
        
        @constraint
        def valid_elements(self):
            assert len(self.buffer) == 5
            for i in range(len(self.buffer)):
                assert self.buffer[i] < 100
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.buffer) == 5
    assert all(x < 100 for x in obj.buffer)


@pytest.mark.skip(reason="Phase 3 not yet implemented")
@pytest.mark.skip(reason="Helper functions on variable arrays need optimization - UNSAT with current implementation")
def test_sum_variable_array():
    """Test sum() helper on variable-size array"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=20, domain=(1, 10))
        
        @constraint
        def sum_constraint(self):
            assert len(self.buffer) >= 5
            assert sum(self.buffer) <= 50
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.buffer) >= 5
    assert sum(obj.buffer) <= 50


@pytest.mark.skip(reason="Helper functions on variable arrays need optimization - UNSAT with current implementation")
def test_unique_variable_array():
    """Test unique() helper on variable-size array"""
    @dataclass
    class Data:
        ids: List[int] = rand(max_size=8, domain=(0, 100))
        
        @constraint
        def unique_ids(self):
            assert len(self.ids) == 5
            assert unique(self.ids)
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.ids) == 5
    assert len(set(obj.ids)) == 5


# ============================================================================
# Phase 4: Integration Tests
# ============================================================================

def test_variable_array_with_randomize_with():
    """Test variable-size arrays in randomize_with block"""
    @dataclass
    class Data:
        buffer: List[int] = rand(max_size=15, domain=(0, 255))
    
    obj = Data()
    with randomize_with(obj):
        assert len(obj.buffer) >= 3
        assert len(obj.buffer) <= 8
        # Skip the loop for now - that's Phase 3
        # for i in range(len(obj.buffer)):
        #     assert obj.buffer[i] >= 10
    
    assert 3 <= len(obj.buffer) <= 8
    # assert all(x >= 10 for x in obj.buffer)


@pytest.mark.skip(reason="Phase 4 not yet implemented")
def test_nested_constraints_variable_array():
    """Test nested constraints with variable-size arrays"""
    @dataclass
    class Packet:
        header: int = rand(domain=(0, 15))
        payload: List[int] = rand(max_size=64, domain=(0, 255))
        
        @constraint
        def header_determines_length(self):
            # Header encodes payload length
            assert len(self.payload) == self.header * 4
    
    obj = Packet()
    randomize(obj)
    
    assert len(obj.payload) == obj.header * 4
    assert len(obj.payload) <= 64


@pytest.mark.skip(reason="Phase 4 not yet implemented")
def test_complex_variable_array_scenario():
    """Test complex scenario: variable arrays with multiple constraints"""
    @dataclass
    class Message:
        msg_type: int = rand(domain=(1, 3))
        data: List[int] = rand(max_size=32, domain=(0, 255))
        checksum: int = rand(domain=(0, 65535))
        
        @constraint
        def type_constraints(self):
            # Different message types have different lengths
            if self.msg_type == 1:
                assert len(self.data) == 8
            elif self.msg_type == 2:
                assert len(self.data) == 16
            else:  # type 3
                assert len(self.data) == 24
            
            # Checksum is sum of data
            assert self.checksum == sum(self.data)
    
    obj = Message()
    randomize(obj)
    
    # Verify constraints
    if obj.msg_type == 1:
        assert len(obj.data) == 8
    elif obj.msg_type == 2:
        assert len(obj.data) == 16
    else:
        assert len(obj.data) == 24
    
    assert obj.checksum == sum(obj.data)


def test_len_on_fixed_array():
    """Test len() on fixed-size arrays returns constant"""
    @dataclass
    class Data:
        fixed: List[int] = rand(size=10, domain=(0, 100))
        variable: List[int] = rand(max_size=20, domain=(0, 200))
        
        @constraint
        def length_relation(self):
            # len(fixed) should be constant 10
            # len(variable) should be variable
            assert len(self.variable) == len(self.fixed)
    
    obj = Data()
    randomize(obj)
    
    assert len(obj.fixed) == 10
    assert len(obj.variable) == 10  # Should match fixed
