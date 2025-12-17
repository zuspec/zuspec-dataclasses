"""Test State Management for Evaluation (Phase 2A)"""
import pytest
from zuspec.dataclasses.rt.eval_state import EvalState


def test_eval_state_read_default():
    """Test that reading uninitialized signals returns 0"""
    state = EvalState()
    
    assert state.read("count") == 0
    assert state.read("child.data") == 0


def test_eval_state_immediate_write():
    """Test immediate write (for comb processes)"""
    state = EvalState()
    
    state.write_immediate("signal_a", 42)
    assert state.read("signal_a") == 42
    
    # Overwrite
    state.write_immediate("signal_a", 100)
    assert state.read("signal_a") == 100


def test_eval_state_deferred_write():
    """Test deferred write (for sync processes)"""
    state = EvalState()
    
    # Set initial value
    state.set_value("count", 5)
    assert state.read("count") == 5
    
    # Deferred write doesn't affect current value
    state.write_deferred("count", 10)
    assert state.read("count") == 5  # Still sees old value
    
    # Commit makes the write visible
    state.commit()
    assert state.read("count") == 10


def test_eval_state_multiple_deferred_writes():
    """Test multiple deferred writes in one cycle"""
    state = EvalState()
    
    state.set_value("a", 1)
    state.set_value("b", 2)
    state.set_value("c", 3)
    
    # Multiple deferred writes
    state.write_deferred("a", 10)
    state.write_deferred("b", 20)
    state.write_deferred("c", 30)
    
    # All reads still see old values
    assert state.read("a") == 1
    assert state.read("b") == 2
    assert state.read("c") == 3
    
    # Commit updates all simultaneously
    state.commit()
    assert state.read("a") == 10
    assert state.read("b") == 20
    assert state.read("c") == 30


def test_eval_state_watchers_on_immediate_write():
    """Test that watchers are triggered on immediate writes"""
    state = EvalState()
    
    triggered = []
    
    def watcher1():
        triggered.append("watcher1")
    
    def watcher2():
        triggered.append("watcher2")
    
    state.register_watcher("signal", watcher1)
    state.register_watcher("signal", watcher2)
    
    # Write should trigger both watchers
    state.write_immediate("signal", 42)
    
    assert triggered == ["watcher1", "watcher2"]


def test_eval_state_watchers_not_triggered_on_same_value():
    """Test that watchers are NOT triggered if value doesn't change"""
    state = EvalState()
    
    state.set_value("signal", 42)
    
    triggered = []
    
    def watcher():
        triggered.append("called")
    
    state.register_watcher("signal", watcher)
    
    # Writing same value should NOT trigger watcher
    state.write_immediate("signal", 42)
    
    assert triggered == []
    
    # Writing different value SHOULD trigger watcher
    state.write_immediate("signal", 100)
    assert triggered == ["called"]


def test_eval_state_watchers_on_commit():
    """Test that watchers are triggered on commit for changed signals"""
    state = EvalState()
    
    state.set_value("a", 1)
    state.set_value("b", 2)
    
    triggered = []
    
    def watcher_a():
        triggered.append("a")
    
    def watcher_b():
        triggered.append("b")
    
    state.register_watcher("a", watcher_a)
    state.register_watcher("b", watcher_b)
    
    # Deferred writes
    state.write_deferred("a", 10)
    state.write_deferred("b", 2)  # Same value
    
    # Commit should trigger only watcher_a (b didn't change)
    state.commit()
    
    assert "a" in triggered
    assert "b" not in triggered


def test_eval_state_deferred_write_last_wins():
    """Test that last deferred write wins"""
    state = EvalState()
    
    state.set_value("signal", 0)
    
    # Multiple deferred writes in same cycle
    state.write_deferred("signal", 10)
    state.write_deferred("signal", 20)
    state.write_deferred("signal", 30)
    
    # Last write wins
    state.commit()
    assert state.read("signal") == 30


def test_eval_state_mixed_immediate_and_deferred():
    """Test mixing immediate and deferred writes"""
    state = EvalState()
    
    # Immediate write (comb process)
    state.write_immediate("comb_out", 42)
    assert state.read("comb_out") == 42
    
    # Deferred write (sync process)
    state.write_deferred("sync_out", 100)
    assert state.read("sync_out") == 0  # Not visible yet
    
    state.commit()
    assert state.read("sync_out") == 100


def test_eval_state_set_value_no_watchers():
    """Test that set_value doesn't trigger watchers"""
    state = EvalState()
    
    triggered = []
    
    def watcher():
        triggered.append("called")
    
    state.register_watcher("signal", watcher)
    
    # set_value should NOT trigger watcher (initialization)
    state.set_value("signal", 42)
    assert triggered == []
    
    # But write_immediate should
    state.write_immediate("signal", 100)
    assert triggered == ["called"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
