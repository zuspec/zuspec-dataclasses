"""Domain classes for constraint solver"""

from abc import ABC, abstractmethod
from typing import Iterator, List, Optional, Set, Tuple
from enum import Enum as PyEnum
import random as _random


class Domain(ABC):
    """Abstract base class for variable domains"""

    @abstractmethod
    def is_empty(self) -> bool:
        """Returns True if domain contains no values"""
        pass

    @abstractmethod
    def is_singleton(self) -> bool:
        """Returns True if domain contains exactly one value"""
        pass

    @abstractmethod
    def size(self) -> int:
        """Returns number of values in domain"""
        pass

    @abstractmethod
    def values(self) -> Iterator[int]:
        """Returns iterator over all values in domain"""
        pass

    @abstractmethod
    def copy(self) -> 'Domain':
        """Returns a copy of this domain"""
        pass


class IntDomain(Domain):
    """Integer domain represented as a list of intervals
    
    Intervals are stored as sorted list of (low, high) tuples where both
    endpoints are inclusive. Intervals are non-overlapping and normalized.
    """

    def __init__(self, intervals: List[Tuple[int, int]], width: int, signed: bool):
        """
        Args:
            intervals: List of (low, high) tuples representing value ranges
            width: Bit-width of the domain (1-64)
            signed: Whether values are signed
        """
        self.width = width
        self.signed = signed
        self._intervals: List[Tuple[int, int]] = []
        
        # Normalize and merge intervals
        if intervals:
            if len(intervals) == 1:
                # Single interval -- no sort/merge needed (common fast path)
                self._intervals = list(intervals)
            else:
                sorted_intervals = sorted(intervals, key=lambda x: x[0])
                current = sorted_intervals[0]
                for interval in sorted_intervals[1:]:
                    if interval[0] <= current[1] + 1:
                        current = (current[0], max(current[1], interval[1]))
                    else:
                        self._intervals.append(current)
                        current = interval
                self._intervals.append(current)

    @classmethod
    def _from_normalized(cls, intervals: List[Tuple[int, int]], width: int, signed: bool) -> 'IntDomain':
        """Fast constructor: intervals must already be sorted, non-overlapping, non-adjacent."""
        obj = object.__new__(cls)
        obj.width = width
        obj.signed = signed
        obj._intervals = intervals
        return obj

    @property
    def min_val(self) -> int:
        """Smallest value in the domain (O(1))."""
        return self._intervals[0][0]

    @property
    def max_val(self) -> int:
        """Largest value in the domain (O(1))."""
        return self._intervals[-1][1]

    @property
    def intervals(self) -> List[Tuple[int, int]]:
        """Returns the list of intervals"""
        return self._intervals

    def is_empty(self) -> bool:
        return len(self._intervals) == 0

    def is_singleton(self) -> bool:
        return len(self._intervals) == 1 and self._intervals[0][0] == self._intervals[0][1]

    def size(self) -> int:
        """Returns total number of values in domain"""
        return sum(high - low + 1 for low, high in self._intervals)

    def values(self) -> Iterator[int]:
        """Yields all values in domain"""
        for low, high in self._intervals:
            for val in range(low, high + 1):
                yield val

    def random_sample(self, rng: _random.Random, n: int) -> List[int]:
        """Return up to *n* distinct random values drawn uniformly from the domain.

        Efficient even for large domains: maps random indices to values using
        cumulative interval sizes, avoiding materialising the whole domain.
        """
        total = self.size()
        if total == 0:
            return []
        if n >= total:
            result = list(self.values())
            rng.shuffle(result)
            return result

        # Fast path for single-interval domains (common case): use randint directly
        if len(self._intervals) == 1:
            lo, hi = self._intervals[0]
            seen = set()
            result = []
            while len(result) < n:
                v = rng.randint(lo, hi)
                if v not in seen:
                    seen.add(v)
                    result.append(v)
            return result

        # Multi-interval: draw n unique indices in [0, total) and map to values.
        indices = sorted(rng.sample(range(total), n))
        result: List[int] = []
        cumulative = 0
        idx_pos = 0
        for lo, hi in self._intervals:
            interval_size = hi - lo + 1
            while idx_pos < len(indices) and indices[idx_pos] < cumulative + interval_size:
                result.append(lo + (indices[idx_pos] - cumulative))
                idx_pos += 1
            cumulative += interval_size
            if idx_pos >= len(indices):
                break

        rng.shuffle(result)
        return result

    def copy(self) -> 'IntDomain':
        """Returns a copy of this domain"""
        return IntDomain._from_normalized(self._intervals.copy(), self.width, self.signed)

    def intersect(self, other: 'IntDomain') -> 'IntDomain':
        """Returns intersection of this domain with another"""
        result_intervals = []
        
        i, j = 0, 0
        while i < len(self._intervals) and j < len(other._intervals):
            lo1, hi1 = self._intervals[i]
            lo2, hi2 = other._intervals[j]
            
            # Compute intersection
            lo = max(lo1, lo2)
            hi = min(hi1, hi2)
            
            if lo <= hi:
                result_intervals.append((lo, hi))
            
            # Advance the interval that ends first
            if hi1 < hi2:
                i += 1
            else:
                j += 1
        
        # Result of intersect is already sorted and non-overlapping
        return IntDomain._from_normalized(result_intervals, self.width, self.signed)

    def union(self, other: 'IntDomain') -> 'IntDomain':
        """Returns union of this domain with another"""
        all_intervals = self._intervals + other._intervals
        return IntDomain(all_intervals, self.width, self.signed)

    def remove_value(self, val: int) -> bool:
        """
        Removes a single value from the domain.
        
        Returns:
            True if domain was modified, False if value wasn't in domain
        """
        new_intervals = []
        modified = False
        
        for low, high in self._intervals:
            if val < low or val > high:
                # Value not in this interval
                new_intervals.append((low, high))
            else:
                # Value is in this interval, split it
                modified = True
                if val > low:
                    new_intervals.append((low, val - 1))
                if val < high:
                    new_intervals.append((val + 1, high))
        
        self._intervals = new_intervals
        return modified

    def remove_range(self, lo: int, hi: int) -> bool:
        """
        Removes a range of values from the domain.
        
        Returns:
            True if domain was modified
        """
        new_intervals = []
        modified = False
        
        for int_low, int_high in self._intervals:
            if hi < int_low or lo > int_high:
                # No overlap
                new_intervals.append((int_low, int_high))
            else:
                # Overlap - split the interval
                modified = True
                if int_low < lo:
                    new_intervals.append((int_low, lo - 1))
                if int_high > hi:
                    new_intervals.append((hi + 1, int_high))
        
        self._intervals = new_intervals
        return modified

    def __repr__(self) -> str:
        if self.is_empty():
            return "IntDomain(empty)"
        intervals_str = ", ".join(f"[{lo}, {hi}]" for lo, hi in self._intervals)
        return f"IntDomain({intervals_str}, width={self.width}, signed={self.signed})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, IntDomain):
            return False
        return (self.width == other.width and 
                self.signed == other.signed and 
                self._intervals == other._intervals)


class BitVectorDomain(IntDomain):
    """
    Integer domain with bit-vector wrapping semantics.
    
    Handles modular arithmetic for operations on bit-vectors.
    """

    def __init__(self, intervals: List[Tuple[int, int]], width: int, signed: bool):
        super().__init__(intervals, width, signed)
        # Ensure all values are within bit-vector range
        self._normalize_to_bitvector()

    def _normalize_to_bitvector(self):
        """Normalize all intervals to valid bit-vector range"""
        if self.signed:
            min_val = -(2 ** (self.width - 1))
            max_val = 2 ** (self.width - 1) - 1
        else:
            min_val = 0
            max_val = 2 ** self.width - 1
        
        # Clip all intervals to valid range
        clipped = []
        for lo, hi in self._intervals:
            clipped_lo = max(min_val, min(max_val, lo))
            clipped_hi = max(min_val, min(max_val, hi))
            if clipped_lo <= clipped_hi:
                clipped.append((clipped_lo, clipped_hi))
        
        self._intervals = clipped

    def copy(self) -> 'BitVectorDomain':
        """Returns a copy of this domain"""
        result = object.__new__(BitVectorDomain)
        result.width = self.width
        result.signed = self.signed
        result._intervals = self._intervals.copy()
        return result


class EnumDomain(Domain):
    """Domain for enumeration types"""

    def __init__(self, values: Set[int], enum_type: Optional[type] = None):
        """
        Args:
            values: Set of integer values representing enum members
            enum_type: Optional Python enum type
        """
        self._values = values.copy()
        self.enum_type = enum_type

    def is_empty(self) -> bool:
        return len(self._values) == 0

    def is_singleton(self) -> bool:
        return len(self._values) == 1

    def size(self) -> int:
        return len(self._values)

    def values(self) -> Iterator[int]:
        return iter(self._values)

    def copy(self) -> 'EnumDomain':
        """Returns a copy of this domain"""
        return EnumDomain(self._values, self.enum_type)

    def intersect(self, other: 'EnumDomain') -> 'EnumDomain':
        """Returns intersection of this domain with another"""
        return EnumDomain(self._values & other._values, self.enum_type)

    def union(self, other: 'EnumDomain') -> 'EnumDomain':
        """Returns union of this domain with another"""
        return EnumDomain(self._values | other._values, self.enum_type)

    def remove_value(self, val: int) -> bool:
        """
        Removes a single value from the domain.
        
        Returns:
            True if domain was modified
        """
        if val in self._values:
            self._values.remove(val)
            return True
        return False

    def __repr__(self) -> str:
        if self.is_empty():
            return "EnumDomain(empty)"
        return f"EnumDomain({self._values})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, EnumDomain):
            return False
        return self._values == other._values and self.enum_type == other.enum_type
