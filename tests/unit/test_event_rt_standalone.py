"""Standalone test for EventRT implementation without full module imports."""

import asyncio
import pytest
import sys
import os

# Direct import of EventRT module without going through package __init__
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/zuspec/dataclasses/rt'))
from event_rt import EventRT


def test_event_rt_basic():
    """Test basic EventRT functionality."""
    evt = EventRT()
    
    assert not evt.is_set()
    
    evt.set()
    assert evt.is_set()
    
    evt.clear()
    assert not evt.is_set()
    
    print("✓ test_event_rt_basic passed")


def test_event_rt_callback_sync():
    """Test that sync callbacks are accepted."""
    evt = EventRT()
    
    callback_invoked = []
    
    def sync_callback():
        callback_invoked.append(True)
    
    # Bind sync callback - should work
    evt.bind_callback(sync_callback)
    evt.set()
    
    # Verify callback was invoked
    assert len(callback_invoked) == 1, "Sync callback should have been invoked"
    
    print("✓ test_event_rt_callback_sync passed")



def test_event_rt_callback_async():
    """Test async callback binding."""
    async def run_test():
        evt = EventRT()
        callback_count = [0]
        callback_executed = asyncio.Event()
        
        async def on_event_async():
            callback_count[0] += 1
            await asyncio.sleep(0.01)
            callback_executed.set()
        
        # Bind async callback
        evt.bind_callback(on_event_async)
        
        # Trigger event
        evt.set()
        
        # Wait for async callback to complete
        await asyncio.wait_for(callback_executed.wait(), timeout=1.0)
        
        assert callback_count[0] == 1
        assert evt.is_set()
        
        print("✓ test_event_rt_callback_async passed")
    
    asyncio.run(run_test())


def test_event_rt_callback_with_await():
    """Test async callback that uses await (e.g., memory access)."""
    async def run_test():
        evt = EventRT()
        results = []
        
        async def callback_with_memory_access():
            """Simulates accessing memory with await."""
            # Simulate async memory read
            await asyncio.sleep(0.01)
            results.append('memory_accessed')
        
        evt.bind_callback(callback_with_memory_access)
        evt.set()
        
        # Wait for callback to complete
        await asyncio.sleep(0.02)
        
        assert results == ['memory_accessed']
        print("✓ test_event_rt_callback_with_await passed")
    
    asyncio.run(run_test())


def test_event_rt_wait():
    """Test wait() functionality."""
    async def run_test():
        evt = EventRT()
        wait_completed = [False]
        
        async def waiter():
            await evt.wait()
            wait_completed[0] = True
        
        # Start waiter
        task = asyncio.create_task(waiter())
        
        # Give waiter time to start
        await asyncio.sleep(0.01)
        
        assert not wait_completed[0]
        
        # Set event
        evt.set()
        
        # Wait for task to complete
        await asyncio.wait_for(task, timeout=1.0)
        
        assert wait_completed[0]
        
        print("✓ test_event_rt_wait passed")
    
    asyncio.run(run_test())


def test_event_rt_wait_and_callback():
    """Test that wait() and callback work together."""
    async def run_test():
        evt = EventRT()
        wait_completed = [False]
        callback_count = [0]
        
        async def on_event():
            callback_count[0] += 1
            await asyncio.sleep(0.01)
        
        evt.bind_callback(on_event)
        
        async def waiter():
            await evt.wait()
            wait_completed[0] = True
        
        # Start waiter
        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)
        
        # Set event - should trigger both waiter and callback
        evt.set()
        
        await asyncio.wait_for(task, timeout=1.0)
        
        # Give callback time to complete
        await asyncio.sleep(0.02)
        
        assert wait_completed[0]
        assert callback_count[0] == 1
        
        print("✓ test_event_rt_wait_and_callback passed")
    
    asyncio.run(run_test())


def test_event_rt_multiple_sets():
    """Test multiple set() calls with callback."""
    async def run_test():
        evt = EventRT()
        callback_counts = []
        
        async def on_event():
            await asyncio.sleep(0.001)
            callback_counts.append(len(callback_counts) + 1)
        
        evt.bind_callback(on_event)
        
        # Set multiple times - each schedules a task
        evt.set()
        evt.set()
        
        # Wait for callbacks to complete
        await asyncio.sleep(0.01)
        
        # Should have 2 callbacks executed
        assert len(callback_counts) == 2
        
        print("✓ test_event_rt_multiple_sets passed")
    
    asyncio.run(run_test())


def test_event_rt_callback_with_state():
    """Test callback that modifies state."""
    async def run_test():
        evt = EventRT()
        
        class Handler:
            def __init__(self):
                self.triggered = False
                self.count = 0
            
            async def on_event(self):
                """Async callback handler."""
                await asyncio.sleep(0.01)
                self.triggered = True
                self.count += 1
        
        handler = Handler()
        evt.bind_callback(handler.on_event)
        
        assert not handler.triggered
        assert handler.count == 0
        
        evt.set()
        
        # Wait for async callback to complete
        await asyncio.sleep(0.02)
        
        assert handler.triggered
        assert handler.count == 1
        
        print("✓ test_event_rt_callback_with_state passed")
    
    asyncio.run(run_test())


async def run_async_tests():
    """Run all async tests."""
    await test_event_rt_callback_async()
    await test_event_rt_callback_with_await()
    await test_event_rt_wait()
    await test_event_rt_wait_and_callback()
    await test_event_rt_callback_with_state()
    await test_event_rt_multiple_sets()


if __name__ == "__main__":
    print("Running EventRT standalone tests...\n")
    
    # Run sync tests
    test_event_rt_basic()
    test_event_rt_callback_sync()
    
    # Run async tests
    asyncio.run(run_async_tests())
    
    print("\n✅ All EventRT tests passed!")
    print("Note: Callbacks must be async methods to support await operations.")
