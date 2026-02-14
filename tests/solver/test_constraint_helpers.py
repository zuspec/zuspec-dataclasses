"""Tests for constraint helper functions (sum, unique, ascending, descending)"""

import pytest
from dataclasses import dataclass
from typing import List
from zuspec.dataclasses import rand, constraint, randomize, randomize_with, sum, unique, ascending, descending


class TestSumHelper:
    """Tests for sum() helper function"""
    
    def test_sum_basic_equality(self):
        """Test sum() in simple equality constraint"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=5, domain=(1, 20))
            
            @constraint
            def sum_constraint(self):
                assert sum(self.arr) == 50
        
        obj = Data()
        randomize(obj)
        
        assert sum(obj.arr) == 50, f"Expected sum=50, got sum={sum(obj.arr)}, arr={obj.arr}"
    
    def test_sum_with_range(self):
        """Test sum() with lower bound"""
        @dataclass
        class Data:
            values: List[int] = rand(size=4, domain=(10, 20))
            
            @constraint
            def range_constraint(self):
                assert sum(self.values) >= 50
        
        obj = Data()
        randomize(obj)
        
        total = sum(obj.values)
        assert total >= 50, f"Sum below minimum: {total}"
    
    def test_sum_in_comparison(self):
        """Test sum() in comparison with another field"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=4, domain=(1, 25))
            threshold: int = rand(domain=(50, 100))
            
            @constraint
            def threshold_constraint(self):
                assert sum(self.arr) < self.threshold
        
        obj = Data()
        randomize(obj)
        
        assert sum(obj.arr) < obj.threshold, f"Sum {sum(obj.arr)} >= threshold {obj.threshold}"
    
    def test_sum_in_randomize_with(self):
        """Test sum() in randomize_with block"""
        @dataclass
        class Data:
            buffer: List[int] = rand(size=6, domain=(0, 20))
        
        obj = Data()
        
        with randomize_with(obj):
            assert sum(obj.buffer) == 60
        
        assert sum(obj.buffer) == 60
    
    def test_sum_multiple_arrays(self):
        """Test sum() with multiple arrays"""
        @dataclass
        class Data:
            arr1: List[int] = rand(size=3, domain=(1, 20))
            arr2: List[int] = rand(size=3, domain=(1, 20))
            
            @constraint
            def balance_constraint(self):
                assert sum(self.arr1) == sum(self.arr2)
        
        obj = Data()
        randomize(obj)
        
        assert sum(obj.arr1) == sum(obj.arr2), f"Sums not equal: {sum(obj.arr1)} vs {sum(obj.arr2)}"
    
    def test_sum_with_arithmetic(self):
        """Test sum() in arithmetic expression"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=3, domain=(1, 10))
            
            @constraint
            def arithmetic_constraint(self):
                assert sum(self.arr) * 2 == 30
        
        obj = Data()
        randomize(obj)
        
        assert sum(obj.arr) * 2 == 30, f"Expected sum*2=30, got {sum(obj.arr)*2}"
    
    def test_sum_edge_case_size_1(self):
        """Test sum() with single-element array"""
        @dataclass
        class Data:
            single: List[int] = rand(size=1, domain=(42, 42))
            
            @constraint
            def single_constraint(self):
                assert sum(self.single) == 42
        
        obj = Data()
        randomize(obj)
        
        assert sum(obj.single) == 42
    
    def test_sum_with_scalar_constraints(self):
        """Test sum() combined with scalar constraints"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=4, domain=(0, 30))
            x: int = rand(domain=(10, 20))
            
            @constraint
            def combined_constraint(self):
                assert sum(self.arr) == 40
                assert self.x > 15
        
        obj = Data()
        randomize(obj)
        
        assert sum(obj.arr) == 40
        assert obj.x > 15
    
    def test_sum_reproducible(self):
        """Test sum() with reproducible randomization"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=5, domain=(1, 20))
            
            @constraint
            def sum_constraint(self):
                assert sum(self.arr) == 55
        
        obj1 = Data()
        randomize(obj1, seed=12345)
        
        obj2 = Data()
        randomize(obj2, seed=12345)
        
        assert obj1.arr == obj2.arr
        assert sum(obj1.arr) == sum(obj2.arr) == 55


class TestUniqueHelper:
    """Tests for unique() helper function"""
    
    def test_unique_basic(self):
        """Test unique() constraint"""
        @dataclass
        class Data:
            ids: List[int] = rand(size=8, domain=(0, 15))
            
            @constraint
            def unique_ids(self):
                assert unique(self.ids)
        
        obj = Data()
        randomize(obj)
        
        assert len(set(obj.ids)) == 8, f"Not all elements unique: {obj.ids}"
    
    def test_unique_small_domain(self):
        """Test unique() with domain exactly matching size"""
        @dataclass
        class Data:
            values: List[int] = rand(size=5, domain=(0, 4))
            
            @constraint
            def all_different(self):
                assert unique(self.values)
        
        obj = Data()
        randomize(obj)
        
        # Should be a permutation of [0,1,2,3,4]
        assert sorted(obj.values) == [0, 1, 2, 3, 4]
    
    def test_unique_with_other_constraints(self):
        """Test unique() combined with other constraints"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=4, domain=(10, 30))
            
            @constraint
            def constraints(self):
                assert unique(self.arr)
                assert self.arr[0] > 15
        
        obj = Data()
        randomize(obj)
        
        assert len(set(obj.arr)) == 4
        assert obj.arr[0] > 15
    
    def test_unique_in_randomize_with(self):
        """Test unique() in randomize_with block"""
        @dataclass
        class Data:
            buffer: List[int] = rand(size=6, domain=(0, 20))
        
        obj = Data()
        
        with randomize_with(obj):
            assert unique(obj.buffer)
        
        assert len(set(obj.buffer)) == 6
    
    def test_unique_edge_case_size_2(self):
        """Test unique() with 2 elements"""
        @dataclass
        class Data:
            pair: List[int] = rand(size=2, domain=(0, 10))
            
            @constraint
            def different(self):
                assert unique(self.pair)
        
        obj = Data()
        randomize(obj)
        
        assert obj.pair[0] != obj.pair[1]
    
    def test_unique_multiple_arrays(self):
        """Test unique() on multiple arrays"""
        @dataclass
        class Data:
            arr1: List[int] = rand(size=4, domain=(0, 10))
            arr2: List[int] = rand(size=4, domain=(0, 10))
            
            @constraint
            def both_unique(self):
                assert unique(self.arr1)
                assert unique(self.arr2)
        
        obj = Data()
        randomize(obj)
        
        assert len(set(obj.arr1)) == 4
        assert len(set(obj.arr2)) == 4


class TestAscendingDescending:
    """Tests for ascending() and descending() helper functions"""
    
    def test_ascending_basic(self):
        """Test ascending() constraint"""
        @dataclass
        class Data:
            values: List[int] = rand(size=5, domain=(0, 50))
            
            @constraint
            def ordered(self):
                assert ascending(self.values)
        
        obj = Data()
        randomize(obj)
        
        for i in range(len(obj.values) - 1):
            assert obj.values[i] < obj.values[i + 1], f"Not ascending at index {i}: {obj.values}"
    
    def test_descending_basic(self):
        """Test descending() constraint"""
        @dataclass
        class Data:
            priorities: List[int] = rand(size=5, domain=(0, 50))
            
            @constraint
            def ordered(self):
                assert descending(self.priorities)
        
        obj = Data()
        randomize(obj)
        
        for i in range(len(obj.priorities) - 1):
            assert obj.priorities[i] > obj.priorities[i + 1], f"Not descending at index {i}: {obj.priorities}"
    
    def test_ascending_with_bound(self):
        """Test ascending() with first element bounded"""
        @dataclass
        class Data:
            seq: List[int] = rand(size=4, domain=(0, 100))
            
            @constraint
            def constraints(self):
                assert ascending(self.seq)
                assert self.seq[0] >= 10
        
        obj = Data()
        randomize(obj)
        
        assert obj.seq[0] >= 10
        for i in range(len(obj.seq) - 1):
            assert obj.seq[i] < obj.seq[i + 1]
    
    def test_descending_with_bound(self):
        """Test descending() with first element bounded"""
        @dataclass
        class Data:
            seq: List[int] = rand(size=4, domain=(0, 100))
            
            @constraint
            def constraints(self):
                assert descending(self.seq)
                assert self.seq[0] <= 90
        
        obj = Data()
        randomize(obj)
        
        assert obj.seq[0] <= 90
        for i in range(len(obj.seq) - 1):
            assert obj.seq[i] > obj.seq[i + 1]
    
    def test_ascending_in_randomize_with(self):
        """Test ascending() in randomize_with block"""
        @dataclass
        class Data:
            data: List[int] = rand(size=5, domain=(0, 100))
        
        obj = Data()
        
        with randomize_with(obj):
            assert ascending(obj.data)
        
        for i in range(len(obj.data) - 1):
            assert obj.data[i] < obj.data[i + 1]
    
    def test_descending_in_randomize_with(self):
        """Test descending() in randomize_with block"""
        @dataclass
        class Data:
            data: List[int] = rand(size=5, domain=(0, 100))
        
        obj = Data()
        
        with randomize_with(obj):
            assert descending(obj.data)
        
        for i in range(len(obj.data) - 1):
            assert obj.data[i] > obj.data[i + 1]
    
    def test_ascending_edge_case_size_2(self):
        """Test ascending() with 2 elements"""
        @dataclass
        class Data:
            pair: List[int] = rand(size=2, domain=(0, 10))
            
            @constraint
            def ordered(self):
                assert ascending(self.pair)
        
        obj = Data()
        randomize(obj)
        
        assert obj.pair[0] < obj.pair[1]


class TestHelpersCombined:
    """Tests combining multiple helper functions"""
    
    def test_unique_and_ascending(self):
        """Test unique() and ascending() together"""
        @dataclass
        class Data:
            seq: List[int] = rand(size=5, domain=(0, 20))
            
            @constraint
            def constraints(self):
                assert unique(self.seq)
                assert ascending(self.seq)
        
        obj = Data()
        randomize(obj)
        
        # Unique
        assert len(set(obj.seq)) == 5
        # Ascending
        for i in range(len(obj.seq) - 1):
            assert obj.seq[i] < obj.seq[i + 1]
    
    def test_unique_and_sum(self):
        """Test unique() and sum() together"""
        @dataclass
        class Data:
            values: List[int] = rand(size=4, domain=(5, 20))
            
            @constraint
            def constraints(self):
                assert unique(self.values)
                assert sum(self.values) == 50
        
        obj = Data()
        randomize(obj)
        
        assert len(set(obj.values)) == 4
        assert sum(obj.values) == 50
    
    def test_ascending_and_sum(self):
        """Test ascending() and sum() together"""
        @dataclass
        class Data:
            arr: List[int] = rand(size=4, domain=(1, 40))
            
            @constraint
            def constraints(self):
                assert ascending(self.arr)
                assert sum(self.arr) >= 30
        
        obj = Data()
        randomize(obj)
        
        # Ascending
        for i in range(len(obj.arr) - 1):
            assert obj.arr[i] < obj.arr[i + 1]
        # Sum
        assert sum(obj.arr) >= 30
