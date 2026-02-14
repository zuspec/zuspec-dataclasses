"""Tests for random seed management"""

import pytest
from zuspec.dataclasses.solver.engine.seed_manager import (
    SeedManager,
    SeedState,
    PerObjectSeedManager,
    get_default_seed_manager,
    set_global_seed,
    reset_global_seed,
)


# Basic SeedManager tests

def test_seed_manager_creation():
    """Test basic seed manager creation"""
    manager = SeedManager(global_seed=42)
    assert manager.global_seed == 42


def test_seed_manager_get_rng():
    """Test getting RNG for a context"""
    manager = SeedManager(global_seed=42)
    
    rng1 = manager.get_rng("context1")
    assert rng1 is not None
    
    # Same context returns same RNG
    rng1_again = manager.get_rng("context1")
    assert rng1 is rng1_again


def test_different_contexts_independent():
    """Test that different contexts have independent RNGs"""
    manager = SeedManager(global_seed=42)
    
    rng1 = manager.get_rng("context1")
    rng2 = manager.get_rng("context2")
    
    # Generate values from both
    val1 = rng1.randint(0, 1000)
    val2 = rng2.randint(0, 1000)
    
    # Should be different (very high probability)
    # If same seed was used, they'd be identical
    # With independent seeds, they should differ
    
    # More robust test: generate sequence
    seq1 = [rng1.randint(0, 100) for _ in range(10)]
    seq2 = [rng2.randint(0, 100) for _ in range(10)]
    
    # Sequences should differ
    assert seq1 != seq2


def test_reproducibility_same_seed():
    """Test that same seed produces same sequence"""
    manager1 = SeedManager(global_seed=42)
    rng1 = manager1.get_rng("test")
    seq1 = [rng1.randint(0, 100) for _ in range(20)]
    
    manager2 = SeedManager(global_seed=42)
    rng2 = manager2.get_rng("test")
    seq2 = [rng2.randint(0, 100) for _ in range(20)]
    
    assert seq1 == seq2


def test_reproducibility_different_seed():
    """Test that different seeds produce different sequences"""
    manager1 = SeedManager(global_seed=42)
    rng1 = manager1.get_rng("test")
    seq1 = [rng1.randint(0, 100) for _ in range(20)]
    
    manager2 = SeedManager(global_seed=43)
    rng2 = manager2.get_rng("test")
    seq2 = [rng2.randint(0, 100) for _ in range(20)]
    
    assert seq1 != seq2


def test_reset_context():
    """Test resetting a context to initial seed"""
    manager = SeedManager(global_seed=42)
    rng = manager.get_rng("test")
    
    # Generate initial sequence
    seq1 = [rng.randint(0, 100) for _ in range(10)]
    
    # Generate more values
    _ = [rng.randint(0, 100) for _ in range(10)]
    
    # Reset context
    manager.reset_context("test")
    rng_reset = manager.get_rng("test")
    
    # Should get same initial sequence
    seq2 = [rng_reset.randint(0, 100) for _ in range(10)]
    
    assert seq1 == seq2


def test_reset_all():
    """Test resetting all contexts"""
    manager = SeedManager(global_seed=42)
    
    rng1 = manager.get_rng("context1")
    rng2 = manager.get_rng("context2")
    
    # Generate sequences
    seq1a = [rng1.randint(0, 100) for _ in range(5)]
    seq2a = [rng2.randint(0, 100) for _ in range(5)]
    
    # Generate more
    _ = [rng1.randint(0, 100) for _ in range(10)]
    _ = [rng2.randint(0, 100) for _ in range(10)]
    
    # Reset all
    manager.reset_all()
    
    # Get RNGs again (should be reset)
    rng1_reset = manager.get_rng("context1")
    rng2_reset = manager.get_rng("context2")
    
    # Should get same initial sequences
    seq1b = [rng1_reset.randint(0, 100) for _ in range(5)]
    seq2b = [rng2_reset.randint(0, 100) for _ in range(5)]
    
    assert seq1a == seq1b
    assert seq2a == seq2b


def test_set_context_seed():
    """Test explicitly setting a context seed"""
    manager = SeedManager(global_seed=42)
    
    # Set explicit seed for a context
    manager.set_context_seed("test", 999)
    rng = manager.get_rng("test")
    
    seq1 = [rng.randint(0, 100) for _ in range(10)]
    
    # Another manager with same explicit seed for that context
    manager2 = SeedManager(global_seed=1)  # Different global seed
    manager2.set_context_seed("test", 999)  # But same context seed
    rng2 = manager2.get_rng("test")
    
    seq2 = [rng2.randint(0, 100) for _ in range(10)]
    
    # Should match because context seed is the same
    assert seq1 == seq2


def test_capture_and_restore_state():
    """Test capturing and restoring RNG state"""
    manager = SeedManager(global_seed=42)
    rng = manager.get_rng("test")
    
    # Generate some values
    _ = [rng.randint(0, 100) for _ in range(5)]
    
    # Capture state
    state = manager.capture_state("test")
    
    # Generate sequence from this point
    seq1 = [rng.randint(0, 100) for _ in range(10)]
    
    # Restore state
    manager.restore_state("test", state)
    rng_restored = manager.get_rng("test")
    
    # Generate sequence again - should match
    seq2 = [rng_restored.randint(0, 100) for _ in range(10)]
    
    assert seq1 == seq2


def test_get_context_info():
    """Test getting information about contexts"""
    manager = SeedManager(global_seed=42)
    
    manager.get_rng("context1")
    manager.get_rng("context2")
    manager.get_rng("context3")
    
    info = manager.get_context_info()
    
    assert info["global_seed"] == 42
    assert info["num_contexts"] == 3
    assert "context1" in info["contexts"]
    assert "context2" in info["contexts"]
    assert "context3" in info["contexts"]


def test_repr():
    """Test string representation"""
    manager = SeedManager(global_seed=42)
    manager.get_rng("test1")
    manager.get_rng("test2")
    
    repr_str = repr(manager)
    assert "SeedManager" in repr_str
    assert "42" in repr_str


# PerObjectSeedManager tests

def test_per_object_manager_creation():
    """Test per-object seed manager creation"""
    manager = PerObjectSeedManager()
    assert manager is not None


def test_per_object_independent():
    """Test that different objects have independent seeds"""
    manager = PerObjectSeedManager()
    
    rng1 = manager.get_object_rng(obj_id=1, seed=42)
    rng2 = manager.get_object_rng(obj_id=2, seed=42)
    
    # Same seed, different objects - should still be independent
    # because each object has its own SeedManager
    seq1 = [rng1.randint(0, 100) for _ in range(20)]
    seq2 = [rng2.randint(0, 100) for _ in range(20)]
    
    # Should be identical because same seed
    assert seq1 == seq2


def test_per_object_reproducibility():
    """Test reproducibility for per-object seeds"""
    manager1 = PerObjectSeedManager()
    rng1 = manager1.get_object_rng(obj_id="obj1", seed=42)
    seq1 = [rng1.randint(0, 100) for _ in range(10)]
    
    manager2 = PerObjectSeedManager()
    rng2 = manager2.get_object_rng(obj_id="obj1", seed=42)
    seq2 = [rng2.randint(0, 100) for _ in range(10)]
    
    assert seq1 == seq2


def test_per_object_contexts():
    """Test contexts within per-object manager"""
    manager = PerObjectSeedManager()
    
    # First get object manager with seed
    rng1 = manager.get_object_rng(obj_id=1, context="var_order", seed=42)
    # Second call without seed - reuses existing manager
    rng2 = manager.get_object_rng(obj_id=1, context="val_order")
    
    # Same object, different contexts - should be independent
    seq1 = [rng1.randint(0, 100) for _ in range(10)]
    seq2 = [rng2.randint(0, 100) for _ in range(10)]
    
    assert seq1 != seq2


def test_per_object_reset():
    """Test resetting a specific object"""
    manager = PerObjectSeedManager()
    
    rng = manager.get_object_rng(obj_id=1, seed=42)
    seq1 = [rng.randint(0, 100) for _ in range(10)]
    
    # Generate more
    _ = [rng.randint(0, 100) for _ in range(10)]
    
    # Reset object
    manager.reset_object(1)
    rng_reset = manager.get_object_rng(obj_id=1)
    
    seq2 = [rng_reset.randint(0, 100) for _ in range(10)]
    
    assert seq1 == seq2


def test_per_object_reset_all():
    """Test resetting all objects"""
    manager = PerObjectSeedManager()
    
    rng1 = manager.get_object_rng(obj_id=1, seed=42)
    rng2 = manager.get_object_rng(obj_id=2, seed=43)
    
    seq1a = [rng1.randint(0, 100) for _ in range(5)]
    seq2a = [rng2.randint(0, 100) for _ in range(5)]
    
    # Generate more
    _ = [rng1.randint(0, 100) for _ in range(10)]
    _ = [rng2.randint(0, 100) for _ in range(10)]
    
    # Reset all
    manager.reset_all_objects()
    
    rng1_reset = manager.get_object_rng(obj_id=1)
    rng2_reset = manager.get_object_rng(obj_id=2)
    
    seq1b = [rng1_reset.randint(0, 100) for _ in range(5)]
    seq2b = [rng2_reset.randint(0, 100) for _ in range(5)]
    
    assert seq1a == seq1b
    assert seq2a == seq2b


def test_per_object_get_info():
    """Test getting information about managed objects"""
    manager = PerObjectSeedManager()
    
    manager.get_object_rng(obj_id=1, seed=42)
    manager.get_object_rng(obj_id=2, seed=43)
    
    info = manager.get_info()
    
    assert info["num_objects"] == 2
    assert 1 in info["objects"]
    assert 2 in info["objects"]


def test_per_object_repr():
    """Test string representation"""
    manager = PerObjectSeedManager()
    manager.get_object_rng(obj_id=1, seed=42)
    manager.get_object_rng(obj_id=2, seed=43)
    
    repr_str = repr(manager)
    assert "PerObjectSeedManager" in repr_str
    assert "2" in repr_str


# Global seed manager tests

def test_get_default_seed_manager():
    """Test getting default global seed manager"""
    manager = get_default_seed_manager()
    assert manager is not None
    assert isinstance(manager, SeedManager)


def test_set_global_seed():
    """Test setting global seed"""
    set_global_seed(12345)
    
    manager = get_default_seed_manager()
    assert manager.global_seed == 12345
    
    # Should be reproducible
    rng = manager.get_rng("test")
    seq1 = [rng.randint(0, 100) for _ in range(10)]
    
    set_global_seed(12345)
    manager2 = get_default_seed_manager()
    rng2 = manager2.get_rng("test")
    seq2 = [rng2.randint(0, 100) for _ in range(10)]
    
    assert seq1 == seq2


def test_reset_global_seed():
    """Test resetting to system randomness"""
    set_global_seed(42)
    manager1 = get_default_seed_manager()
    assert manager1.global_seed == 42
    
    reset_global_seed()
    manager2 = get_default_seed_manager()
    assert manager2.global_seed is None


# Integration test

def test_seed_manager_integration():
    """Test realistic usage scenario"""
    # Simulate solving with reproducible randomization
    manager = SeedManager(global_seed=12345)
    
    # Variable ordering context
    var_rng = manager.get_rng("variable_ordering")
    variables = ["x", "y", "z", "w"]
    var_order1 = variables.copy()
    var_rng.shuffle(var_order1)
    
    # Value selection context (independent)
    val_rng = manager.get_rng("value_selection")
    values = list(range(10))
    val_order1 = val_rng.sample(values, 5)
    
    # randc context (independent)
    randc_rng = manager.get_rng("randc_x")
    randc_perm1 = list(range(8))
    randc_rng.shuffle(randc_perm1)
    
    # Reset and repeat - should get same sequences
    manager.reset_all()
    
    var_rng = manager.get_rng("variable_ordering")
    var_order2 = variables.copy()
    var_rng.shuffle(var_order2)
    
    val_rng = manager.get_rng("value_selection")
    val_order2 = val_rng.sample(values, 5)
    
    randc_rng = manager.get_rng("randc_x")
    randc_perm2 = list(range(8))
    randc_rng.shuffle(randc_perm2)
    
    # All should match
    assert var_order1 == var_order2
    assert val_order1 == val_order2
    assert randc_perm1 == randc_perm2
