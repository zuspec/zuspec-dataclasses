"""Test Event with 'at' bind site for callback binding."""

import asyncio
import pytest
import zuspec.dataclasses as zdc


@zdc.dataclass
class InterruptController(zdc.Component):
    """Simple interrupt controller with an event."""
    irq: zdc.Event = zdc.field(default_factory=zdc.Event)
    callback_count: int = zdc.field(default=0)
    
    def __bind__(self):
        """Bind the callback to the event's 'at' bind site."""
        return {
            self.irq.at: self.on_interrupt
        }
    
    def on_interrupt(self):
        """Callback invoked when IRQ is set."""
        self.callback_count += 1
    
    def trigger_irq(self):
        """Trigger the interrupt."""
        self.irq.set()


@zdc.dataclass 
class SyncCallbackController(zdc.Component):
    """Interrupt controller - callbacks must be sync, not async."""
    irq: zdc.Event = zdc.field(default_factory=zdc.Event)
    callback_count: int = zdc.field(default=0)
    
    def __bind__(self):
        """Bind the sync callback to the event."""
        return {
            self.irq.at: self.on_interrupt
        }
    
    def on_interrupt(self):
        """Synchronous callback invoked when IRQ is set."""
        self.callback_count += 1
    
    def trigger_irq(self):
        """Trigger the interrupt."""
        self.irq.set()


@zdc.dataclass
class EventUser(zdc.Component):
    """Component that uses an event and waits on it."""
    evt: zdc.Event = zdc.field(default_factory=zdc.Event)
    wait_completed: bool = zdc.field(default=False)
    
    @zdc.process
    async def wait_for_event(self):
        """Process that waits for the event."""
        await self.evt.wait()
        self.wait_completed = True


def test_event_callback_sync():
    """Test synchronous callback bound to Event.at."""
    ic = InterruptController()
    
    assert ic.callback_count == 0
    
    # Trigger interrupt - should invoke callback
    ic.trigger_irq()
    
    assert ic.callback_count == 1
    assert ic.irq.is_set()
    
    # Trigger again
    ic.irq.clear()
    ic.trigger_irq()
    
    assert ic.callback_count == 2


def test_event_callback_sync_only():
    """Test that callbacks work and must be synchronous."""
    ic = SyncCallbackController()
    
    assert ic.callback_count == 0
    
    # Trigger interrupt - should invoke callback
    ic.trigger_irq()
    
    assert ic.callback_count == 1


def test_event_wait_and_callback():
    """Test that both wait() and callback work together."""
    async def run_test():
        ic = InterruptController()
        eu = EventUser()
        
        # Share the same event between components
        eu.evt = ic.irq
        
        # Create a simple waiter task instead of using process decorator
        async def wait_on_event():
            await eu.evt.wait()
            eu.wait_completed = True
        
        wait_task = asyncio.create_task(wait_on_event())
        
        # Give it a moment to start waiting
        await asyncio.sleep(0.01)
        
        assert not eu.wait_completed
        assert ic.callback_count == 0
        
        # Trigger the interrupt
        ic.trigger_irq()
        
        # Wait for the waiter to complete
        await asyncio.wait_for(wait_task, timeout=1.0)
        
        # Both callback and waiter should have been triggered
        assert eu.wait_completed
        assert ic.callback_count == 1
    
    asyncio.run(run_test())


def test_event_without_callback():
    """Test Event works without a callback bound."""
    evt = zdc.Event()
    
    assert not evt.is_set()
    
    evt.set()
    assert evt.is_set()
    
    evt.clear()
    assert not evt.is_set()


def test_event_wait_without_callback():
    """Test Event.wait() works without callback."""
    async def run_test():
        evt = zdc.Event()
        
        async def waiter():
            await evt.wait()
            return True
        
        task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)
        
        evt.set()
        result = await asyncio.wait_for(task, timeout=1.0)
        
        assert result is True
    
    asyncio.run(run_test())


@zdc.dataclass
class MultiEventController(zdc.Component):
    """Controller with multiple events."""
    irq1: zdc.Event = zdc.field(default_factory=zdc.Event)
    irq2: zdc.Event = zdc.field(default_factory=zdc.Event)
    irq1_count: int = zdc.field(default=0)
    irq2_count: int = zdc.field(default=0)
    
    def __bind__(self):
        """Bind different callbacks to different events."""
        return {
            self.irq1.at: self.on_irq1,
            self.irq2.at: self.on_irq2
        }
    
    def on_irq1(self):
        self.irq1_count += 1
    
    def on_irq2(self):
        self.irq2_count += 1


def test_multiple_events():
    """Test multiple events with different callbacks."""
    mc = MultiEventController()
    
    assert mc.irq1_count == 0
    assert mc.irq2_count == 0
    
    # Trigger first event
    mc.irq1.set()
    assert mc.irq1_count == 1
    assert mc.irq2_count == 0
    
    # Trigger second event
    mc.irq2.set()
    assert mc.irq1_count == 1
    assert mc.irq2_count == 1
    
    # Trigger first again
    mc.irq1.clear()
    mc.irq1.set()
    assert mc.irq1_count == 2
    assert mc.irq2_count == 1


if __name__ == "__main__":
    test_event_callback_sync()
    test_event_callback_sync_only()
    test_event_without_callback()
    asyncio.run(test_event_wait_and_callback())
    asyncio.run(test_event_wait_without_callback())
    test_multiple_events()
    print("All tests passed!")
    print("Note: Event callbacks must be synchronous Python methods.")
