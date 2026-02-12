"""Tests for Domain classes"""

import pytest
from zuspec.dataclasses.solver.core.domain import IntDomain, EnumDomain, BitVectorDomain


class TestIntDomain:
    """Test IntDomain functionality"""
    
    def test_creation_single_interval(self):
        """Test creating domain with single interval"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        assert not domain.is_empty()
        assert domain.size() == 11
        assert list(domain.values()) == list(range(11))
    
    def test_creation_multiple_intervals(self):
        """Test creating domain with multiple intervals"""
        domain = IntDomain([(0, 5), (10, 15)], width=32, signed=False)
        assert domain.size() == 12
        expected = list(range(6)) + list(range(10, 16))
        assert list(domain.values()) == expected
    
    def test_merge_overlapping_intervals(self):
        """Test that overlapping intervals are merged"""
        domain = IntDomain([(0, 5), (3, 8), (7, 10)], width=32, signed=False)
        # Should merge into single interval [0, 10]
        assert domain.size() == 11
        assert len(domain.intervals) == 1
        assert domain.intervals[0] == (0, 10)
    
    def test_merge_adjacent_intervals(self):
        """Test that adjacent intervals are merged"""
        domain = IntDomain([(0, 5), (6, 10)], width=32, signed=False)
        # Should merge into single interval [0, 10]
        assert len(domain.intervals) == 1
        assert domain.intervals[0] == (0, 10)
    
    def test_singleton(self):
        """Test singleton domain"""
        domain = IntDomain([(5, 5)], width=32, signed=False)
        assert domain.is_singleton()
        assert domain.size() == 1
        assert list(domain.values()) == [5]
    
    def test_empty(self):
        """Test empty domain"""
        domain = IntDomain([], width=32, signed=False)
        assert domain.is_empty()
        assert domain.size() == 0
        assert list(domain.values()) == []
    
    def test_intersect(self):
        """Test intersection of domains"""
        d1 = IntDomain([(0, 10)], width=32, signed=False)
        d2 = IntDomain([(5, 15)], width=32, signed=False)
        
        result = d1.intersect(d2)
        assert result.size() == 6
        assert list(result.values()) == list(range(5, 11))
    
    def test_intersect_disjoint(self):
        """Test intersection of disjoint domains"""
        d1 = IntDomain([(0, 5)], width=32, signed=False)
        d2 = IntDomain([(10, 15)], width=32, signed=False)
        
        result = d1.intersect(d2)
        assert result.is_empty()
    
    def test_union(self):
        """Test union of domains"""
        d1 = IntDomain([(0, 5)], width=32, signed=False)
        d2 = IntDomain([(10, 15)], width=32, signed=False)
        
        result = d1.union(d2)
        assert result.size() == 12
        expected = list(range(6)) + list(range(10, 16))
        assert list(result.values()) == expected
    
    def test_remove_value_in_middle(self):
        """Test removing value from middle of interval"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        modified = domain.remove_value(5)
        
        assert modified
        assert domain.size() == 10
        assert len(domain.intervals) == 2
        assert domain.intervals == [(0, 4), (6, 10)]
    
    def test_remove_value_at_start(self):
        """Test removing value at start of interval"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        modified = domain.remove_value(0)
        
        assert modified
        assert domain.size() == 10
        assert len(domain.intervals) == 1
        assert domain.intervals == [(1, 10)]
    
    def test_remove_value_at_end(self):
        """Test removing value at end of interval"""
        domain = IntDomain([(0, 10)], width=32, signed=False)
        modified = domain.remove_value(10)
        
        assert modified
        assert domain.size() == 10
        assert len(domain.intervals) == 1
        assert domain.intervals == [(0, 9)]
    
    def test_remove_value_not_in_domain(self):
        """Test removing value not in domain"""
        domain = IntDomain([(0, 5), (10, 15)], width=32, signed=False)
        modified = domain.remove_value(7)
        
        assert not modified
        assert domain.size() == 12
    
    def test_remove_range(self):
        """Test removing range of values"""
        domain = IntDomain([(0, 20)], width=32, signed=False)
        modified = domain.remove_range(5, 15)
        
        assert modified
        assert domain.size() == 10
        assert len(domain.intervals) == 2
        assert domain.intervals == [(0, 4), (16, 20)]
    
    def test_copy(self):
        """Test copying domain"""
        domain = IntDomain([(0, 10), (20, 30)], width=32, signed=False)
        copy = domain.copy()
        
        assert copy == domain
        assert copy is not domain
        
        # Modify copy
        copy.remove_value(5)
        assert copy != domain


class TestBitVectorDomain:
    """Test BitVectorDomain with wrapping semantics"""
    
    def test_unsigned_normalization(self):
        """Test that values are normalized to unsigned range"""
        domain = BitVectorDomain([(0, 255)], width=8, signed=False)
        assert domain.size() == 256
    
    def test_signed_normalization(self):
        """Test that values are normalized to signed range"""
        domain = BitVectorDomain([(-128, 127)], width=8, signed=True)
        assert domain.size() == 256
    
    def test_out_of_range_clipping(self):
        """Test that out-of-range values are clipped"""
        # Try to create domain with values outside 8-bit unsigned range
        domain = BitVectorDomain([(-10, 300)], width=8, signed=False)
        # Should be clipped to [0, 255]
        assert domain.intervals[0] == (0, 255)


class TestEnumDomain:
    """Test EnumDomain functionality"""
    
    def test_creation(self):
        """Test creating enum domain"""
        domain = EnumDomain({1, 2, 3, 4, 5})
        assert domain.size() == 5
        assert set(domain.values()) == {1, 2, 3, 4, 5}
    
    def test_singleton(self):
        """Test singleton enum domain"""
        domain = EnumDomain({42})
        assert domain.is_singleton()
        assert list(domain.values()) == [42]
    
    def test_empty(self):
        """Test empty enum domain"""
        domain = EnumDomain(set())
        assert domain.is_empty()
        assert list(domain.values()) == []
    
    def test_intersect(self):
        """Test intersection of enum domains"""
        d1 = EnumDomain({1, 2, 3, 4, 5})
        d2 = EnumDomain({3, 4, 5, 6, 7})
        
        result = d1.intersect(d2)
        assert set(result.values()) == {3, 4, 5}
    
    def test_union(self):
        """Test union of enum domains"""
        d1 = EnumDomain({1, 2, 3})
        d2 = EnumDomain({4, 5, 6})
        
        result = d1.union(d2)
        assert set(result.values()) == {1, 2, 3, 4, 5, 6}
    
    def test_remove_value(self):
        """Test removing value from enum domain"""
        domain = EnumDomain({1, 2, 3, 4, 5})
        modified = domain.remove_value(3)
        
        assert modified
        assert set(domain.values()) == {1, 2, 4, 5}
    
    def test_remove_value_not_present(self):
        """Test removing value not in domain"""
        domain = EnumDomain({1, 2, 3})
        modified = domain.remove_value(5)
        
        assert not modified
        assert set(domain.values()) == {1, 2, 3}
    
    def test_copy(self):
        """Test copying enum domain"""
        domain = EnumDomain({1, 2, 3, 4, 5})
        copy = domain.copy()
        
        assert copy == domain
        assert copy is not domain
        
        # Modify copy
        copy.remove_value(3)
        assert copy != domain
