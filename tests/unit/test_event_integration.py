"""
Integration example showing Event 'at' bind site usage in a realistic scenario.

This example demonstrates:
1. Event fields in components
2. Binding callbacks to events using __bind__()
3. Interaction between components via events
4. Both sync and async callback handlers
"""

import asyncio
import sys
import os

# Direct import to avoid Python version issues
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/zuspec/dataclasses/rt'))
from event_rt import EventRT


class SimpleDevice:
    """Simulates a hardware device with interrupt capability."""
    def __init__(self):
        self.irq = EventRT()
        self.data_ready_count = 0
        self._bind_callbacks()
    
    def _bind_callbacks(self):
        """Simulate the __bind__() method that would bind callbacks."""
        self.irq.bind_callback(self.on_interrupt)
    
    async def on_interrupt(self):
        """Async callback invoked when interrupt fires."""
        # Simulate memory access
        await asyncio.sleep(0.001)
        self.data_ready_count += 1
        print(f"  → Device interrupt handler: data_ready_count = {self.data_ready_count}")
    
    def trigger_interrupt(self):
        """Simulate hardware asserting interrupt line."""
        print("  Device: Triggering interrupt...")
        self.irq.set()


class InterruptController:
    """Simulates an interrupt controller that routes device interrupts."""
    def __init__(self, device: SimpleDevice):
        self.device = device
        self.irq_received = EventRT()
        self.irq_count = 0
        # Note: We create our own event and don't override device's callback
        # In a real scenario, the controller would monitor the device's event
        self._bind_callbacks()
    
    def _bind_callbacks(self):
        """Bind to our own event for system acknowledgment."""
        self.irq_received.bind_callback(self.on_system_ack)
    
    def forward_interrupt(self):
        """Manually forward interrupt (called by device handler)."""
        self.irq_count += 1
        print(f"  → IRQ Controller: Forwarding interrupt #{self.irq_count}")
        # Forward to system
        self.irq_received.set()
    
    async def on_system_ack(self):
        """Async callback when system acknowledges interrupt."""
        await asyncio.sleep(0.001)
        print(f"  → IRQ Controller: System acknowledged interrupt")


async def test_simple_interrupt_flow():
    """Test basic interrupt flow from device to handler."""
    print("\n=== Test 1: Simple Interrupt Flow ===")
    
    device = SimpleDevice()
    
    print("Initial state:")
    print(f"  data_ready_count = {device.data_ready_count}")
    
    print("\nTriggering interrupt:")
    device.trigger_interrupt()
    
    # Wait for async callback to complete
    await asyncio.sleep(0.01)
    
    print("\nFinal state:")
    print(f"  data_ready_count = {device.data_ready_count}")
    
    assert device.data_ready_count == 1
    print("✓ Test passed")


async def test_interrupt_controller_flow():
    """Test interrupt routing through controller."""
    print("\n=== Test 2: Interrupt Controller Flow ===")
    print("(Each event can have one callback; controller has its own event)")
    
    device = SimpleDevice()
    controller = InterruptController(device)
    
    print("Initial state:")
    print(f"  device.data_ready_count = {device.data_ready_count}")
    print(f"  controller.irq_count = {controller.irq_count}")
    
    print("\nTriggering device interrupt:")
    device.trigger_interrupt()
    
    # Wait for device callback
    await asyncio.sleep(0.01)
    
    # Device handler fires, now controller forwards
    print("\nController forwarding interrupt:")
    controller.forward_interrupt()
    
    await asyncio.sleep(0.01)  # Wait for controller callback
    
    print("\nFinal state:")
    print(f"  device.data_ready_count = {device.data_ready_count}")
    print(f"  controller.irq_count = {controller.irq_count}")
    
    assert device.data_ready_count == 1
    assert controller.irq_count == 1
    print("✓ Test passed")


def test_callback_must_be_async():
    """Test that sync callbacks are rejected."""
    print("\n=== Test 3: Callback Must Be Async ===")
    
    evt = EventRT()
    
    def sync_callback():
        pass
    
    print("Attempting to bind sync callback...")
    try:
        evt.bind_callback(sync_callback)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        print(f"  → Correctly rejected: {e}")
    
    print("✓ Test passed")


class WaitAndCallbackDevice:
    """Device demonstrating both wait() and callback usage."""
    def __init__(self):
        self.irq = EventRT()
        self.callback_handled = False
        self.wait_handled = False
        self._bind_callbacks()
    
    def _bind_callbacks(self):
        self.irq.bind_callback(self.on_interrupt_callback)
    
    async def on_interrupt_callback(self):
        """Async callback handler."""
        await asyncio.sleep(0.001)
        self.callback_handled = True
        print(f"  → Callback: Immediate handler executed")
    
    async def wait_for_interrupt(self):
        """Background task waiting for interrupt."""
        print(f"  → Wait task: Waiting for interrupt...")
        await self.irq.wait()
        self.wait_handled = True
        print(f"  → Wait task: Interrupt received")
    
    def trigger_interrupt(self):
        print("  Device: Triggering interrupt...")
        self.irq.set()


async def test_wait_and_callback():
    """Test that both wait() and callback work together."""
    print("\n=== Test 4: Wait and Callback Together ===")
    
    device = WaitAndCallbackDevice()
    
    print("Initial state:")
    print(f"  callback_handled = {device.callback_handled}")
    print(f"  wait_handled = {device.wait_handled}")
    
    # Start background waiter
    print("\nStarting background waiter...")
    wait_task = asyncio.create_task(device.wait_for_interrupt())
    await asyncio.sleep(0.01)
    
    print("\nTriggering interrupt:")
    device.trigger_interrupt()
    
    # Wait for background task
    await asyncio.wait_for(wait_task, timeout=1.0)
    
    # Give callback time to complete
    await asyncio.sleep(0.01)
    
    print("\nFinal state:")
    print(f"  callback_handled = {device.callback_handled}")
    print(f"  wait_handled = {device.wait_handled}")
    
    assert device.callback_handled
    assert device.wait_handled
    print("✓ Test passed")


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Event 'at' Bind Site - Integration Examples")
    print("=" * 60)
    
    await test_simple_interrupt_flow()
    await test_interrupt_controller_flow()
    test_callback_must_be_async()
    await test_wait_and_callback()
    
    print("\n" + "=" * 60)
    print("✅ All integration tests passed!")
    print("Note: Callbacks must be async methods to support await.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
