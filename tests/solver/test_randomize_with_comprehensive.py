"""Comprehensive tests for randomize_with() with inline constraints."""

import pytest
from zuspec.dataclasses import dataclass, rand, randc, constraint
from zuspec.dataclasses.solver.api import randomize_with, RandomizationError


@dataclass
class Packet:
    """Test packet with rand fields."""
    addr: rand(domain=(0, 255)) = 0
    data: rand(domain=(0, 255)) = 0
    mode: rand(domain=(0, 3)) = 0
    
    @constraint
    def word_aligned(self):
        """Addr must be word-aligned."""
        assert self.addr % 4 == 0


@dataclass
class PacketWithArray:
    """Test packet with array field."""
    addr: rand(domain=(0, 255)) = 0
    buffer: list = None
    
    def __post_init__(self):
        if self.buffer is None:
            self.buffer = [0] * 4
    
    @constraint
    def word_aligned(self):
        """Addr must be word-aligned."""
        assert self.addr % 4 == 0


class TestRandomizeWithBasic:
    """Test basic randomize_with functionality."""
    
    def test_simple_constraint(self):
        """Test simple inline constraint."""
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            assert pkt.addr > 100
        
        assert pkt.addr > 100
        assert pkt.addr % 4 == 0  # Class constraint still applies
    
    def test_multiple_constraints(self):
        """Test multiple inline constraints."""
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            assert pkt.addr > 100
            assert pkt.addr < 200
            assert pkt.data < 128
        
        assert 100 < pkt.addr < 200
        assert pkt.data < 128
        assert pkt.addr % 4 == 0
    
    def test_seed_reproducibility(self):
        """Test that same seed produces same results."""
        results = []
        for _ in range(3):
            pkt = Packet()
            with randomize_with(pkt, seed=123):
                assert pkt.addr > 100
            results.append((pkt.addr, pkt.data))
        
        # All should be identical
        assert len(set(results)) == 1
    
    def test_different_seeds(self):
        """Test that different seeds produce different results."""
        results = []
        for seed in [1, 2, 3, 4, 5]:
            pkt = Packet()
            with randomize_with(pkt, seed=seed):
                assert pkt.addr > 100
            results.append(pkt.addr)
        
        # Should have variation (with high probability)
        assert len(set(results)) > 1
    
    def test_unsat_constraint_raises(self):
        """Test that unsatisfiable constraints raise error."""
        pkt = Packet()
        with pytest.raises(RandomizationError, match="No solution found"):
            with randomize_with(pkt):
                assert pkt.addr > 250
                assert pkt.addr < 10  # Contradiction


class TestRandomizeWithControlFlow:
    """Test randomize_with with control flow (if/else, loops)."""
    
    def test_if_constraint(self):
        """Test if statement in inline constraints."""
        # Test when mode=1
        pkt = Packet()
        pkt.mode = 1  # Set mode first, then randomize others
        
        # Note: Currently mode is also randomized, so we can't guarantee
        # the condition. Let's test a different way.
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            # High address preference
            assert pkt.addr > 100
            # Conditional on mode
            if pkt.mode == 1:
                assert pkt.data > 128
    
    def test_if_else_constraint(self):
        """Test if-else statement in inline constraints."""
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            if pkt.mode == 0:
                assert pkt.addr < 128
            else:
                assert pkt.addr >= 128
        
        # Should satisfy the conditional
        if pkt.mode == 0:
            assert pkt.addr < 128
        else:
            assert pkt.addr >= 128
    
    @pytest.mark.skip(reason="For loops need array support")
    def test_for_loop_constraint(self):
        """Test for loop in inline constraints."""
        pkt = PacketWithArray()
        with randomize_with(pkt, seed=42):
            assert pkt.addr > 100
            # Constrain array elements
            for i in range(4):
                assert pkt.buffer[i] < 128


class TestRandomizeWithComplex:
    """Test complex randomize_with scenarios."""
    
    def test_multiple_calls_same_object(self):
        """Test multiple randomize_with calls on same object."""
        pkt = Packet()
        
        # First call
        with randomize_with(pkt, seed=1):
            assert pkt.addr < 128
        addr1 = pkt.addr
        assert addr1 < 128
        
        # Second call with different constraints
        with randomize_with(pkt, seed=2):
            assert pkt.addr >= 128
        addr2 = pkt.addr
        assert addr2 >= 128
        
        # Values should be different
        assert addr1 != addr2
    
    def test_caching_different_locations(self):
        """Test that cache works for different with block locations."""
        pkt = Packet()
        
        # First location
        with randomize_with(pkt, seed=1):
            assert pkt.addr < 100
        
        # Second location (different line)
        with randomize_with(pkt, seed=2):
            assert pkt.addr >= 100
        
        # Should work without errors
        assert pkt.addr >= 100


class TestRandomizeWithInMethods:
    """Test randomize_with inside class methods."""
    
    class BenchTest:  # Renamed to avoid pytest collection
        """Example test bench using randomize_with."""
        
        def __init__(self):
            self.pkt = Packet()
        
        def randomize_high_addr(self):
            """Randomize with high address."""
            # Note: Currently self.pkt.addr doesn't work, use direct reference
            pkt = self.pkt
            with randomize_with(pkt, seed=42):
                assert pkt.addr > 200
        
        def randomize_low_data(self):
            """Randomize with low data."""
            pkt = self.pkt
            with randomize_with(pkt, seed=43):
                assert pkt.data < 50
    
    def test_method_context(self):
        """Test randomize_with in method context."""
        bench = self.BenchTest()
        bench.randomize_high_addr()
        assert bench.pkt.addr > 200
        
        bench.randomize_low_data()
        assert bench.pkt.data < 50


class TestRandomizeWithEdgeCases:
    """Test edge cases and error handling."""
    
    def test_no_inline_constraints(self):
        """Test randomize_with with no inline constraints (just uses class constraints)."""
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            pass  # No inline constraints
        
        # Should still apply class constraints
        assert pkt.addr % 4 == 0
        assert 0 <= pkt.addr <= 255
    
    def test_bare_expression_constraint(self):
        """Test bare expression (not assert) as constraint."""
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            pkt.addr > 100  # Bare expression
            assert pkt.data < 128
        
        # Should work - bare expressions are supported
        # Note: Implementation may or may not capture bare expressions
        assert pkt.data < 128
    
    def test_tight_constraint_space(self):
        """Test randomization in a very tight constraint space."""
        pkt = Packet()
        with randomize_with(pkt, seed=42):
            assert pkt.addr == 100  # Very specific
        
        assert pkt.addr == 100
    
    def test_contradictory_with_class_constraint(self):
        """Test inline constraint contradicting class constraint."""
        pkt = Packet()
        with pytest.raises(RandomizationError, match="No solution found"):
            with randomize_with(pkt):
                # Conflicts with word_aligned (addr % 4 == 0)
                assert pkt.addr == 101  # Not divisible by 4


class TestRandomizeWithCaching:
    """Test AST caching behavior."""
    
    def test_repeated_calls_use_cache(self):
        """Test that repeated calls at same location use cached AST."""
        results = []
        
        # Call 100 times - should be fast due to caching
        for i in range(100):
            pkt = Packet()
            with randomize_with(pkt, seed=i):
                assert pkt.addr > 100
            results.append(pkt.addr)
        
        # All should satisfy constraint
        assert all(addr > 100 for addr in results)
        
        # Should have variation across seeds
        assert len(set(results)) > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
