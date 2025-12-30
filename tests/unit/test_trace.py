import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt import with_tracer, Thread
from typing import Dict, Any, Optional

def test_smoke():

    @zdc.dataclass
    class MyC(zdc.Component):

        async def run(self, a : zdc.u32) -> zdc.u32:
            await self.wait(zdc.Time.ns(10))
            return a+15
        
    class Monitor:

        def __init__(self):
            self.events = []

        def enter(self, m : str, thread : Thread, time_ns : float, args : Dict[str,Any]):
            self.events.append(('enter', m, thread, time_ns, args))

        def leave(self, m : str, thread : Thread, time_ns : float, ret : Any, exc : Optional[Exception]):
            self.events.append(('leave', m, thread, time_ns, ret, exc))

    m = Monitor()

    # Use a context manager to enable tracing
    with with_tracer(m):
        c = MyC()

    v = asyncio.run(c.run(20))

    assert v == 35
    
    # Verify tracing events
    assert len(m.events) == 2
    
    # Check enter event
    event_type, method, thread, enter_time, args = m.events[0]
    assert event_type == 'enter'
    assert method == 'run'
    assert isinstance(thread, Thread)
    assert thread.tid == 0
    assert thread.parent is None
    assert thread.component is None
    assert enter_time == 0.0  # Enter at time 0
    assert args == {'a': 20}
    
    # Check leave event  
    event_type, method, thread, leave_time, ret, exc = m.events[1]
    assert event_type == 'leave'
    assert method == 'run'
    assert isinstance(thread, Thread)
    assert thread.tid == 0
    assert leave_time == 10.0  # Leave at time 10ns (after wait)
    assert ret == 35
    assert exc is None

def test_no_tracer():
    """Test that methods work correctly without tracing enabled."""
    
    @zdc.dataclass
    class MyC(zdc.Component):

        async def run(self, a : zdc.u32) -> zdc.u32:
            await self.wait(zdc.Time.ns(10))
            return a+15
    
    # Create component without tracing
    c = MyC()
    v = asyncio.run(c.run(20))
    
    assert v == 35

def test_multiple_calls_with_timestamps():
    """Test that multiple method calls are traced with correct timestamps."""
    
    @zdc.dataclass
    class MyC(zdc.Component):

        async def step1(self) -> zdc.u32:
            await self.wait(zdc.Time.ns(5))
            return 10
        
        async def step2(self, x : zdc.u32) -> zdc.u32:
            await self.wait(zdc.Time.ns(7))
            return x + 20
        
        async def run(self) -> zdc.u32:
            v1 = await self.step1()
            v2 = await self.step2(v1)
            return v2
        
    class Monitor:

        def __init__(self):
            self.events = []

        def enter(self, m : str, thread : Thread, time_ns : float, args : Dict[str,Any]):
            self.events.append(('enter', m, thread, time_ns, args))

        def leave(self, m : str, thread : Thread, time_ns : float, ret : Any, exc : Optional[Exception]):
            self.events.append(('leave', m, thread, time_ns, ret, exc))

    m = Monitor()

    # Use a context manager to enable tracing
    with with_tracer(m):
        c = MyC()

    v = asyncio.run(c.run())

    assert v == 30
    
    # Verify we have 6 events: enter/leave for run, step1, step2
    assert len(m.events) == 6
    
    # All calls should share the same thread (nested execution)
    threads = [e[2] for e in m.events]
    tids = [t.tid for t in threads]
    assert len(set(tids)) == 1, f"Expected single thread ID, got {set(tids)}"
    
    # run.enter at t=0
    event = m.events[0]
    assert event[0] == 'enter' and event[1] == 'run' and event[3] == 0.0
    
    # step1.enter at t=0
    event = m.events[1]
    assert event[0] == 'enter' and event[1] == 'step1' and event[3] == 0.0
    
    # step1.leave at t=5
    event = m.events[2]
    assert event[0] == 'leave' and event[1] == 'step1' and event[3] == 5.0 and event[4] == 10
    
    # step2.enter at t=5
    event = m.events[3]
    assert event[0] == 'enter' and event[1] == 'step2' and event[3] == 5.0 and event[4] == {'x': 10}
    
    # step2.leave at t=12 (5 + 7)
    event = m.events[4]
    assert event[0] == 'leave' and event[1] == 'step2' and event[3] == 12.0 and event[4] == 30
    
    # run.leave at t=12
    event = m.events[5]
    assert event[0] == 'leave' and event[1] == 'run' and event[3] == 12.0 and event[4] == 30

def test_concurrent_threads_with_nested_calls():
    """Test that concurrent threads get unique task IDs and nested calls maintain thread context."""
    
    @zdc.dataclass
    class Worker(zdc.Component):

        async def sub_task(self, worker_id: zdc.u32, value: zdc.u32) -> zdc.u32:
            """Nested method called from main_task."""
            await self.wait(zdc.Time.ns(2))
            return value * worker_id
        
        async def main_task(self, worker_id: zdc.u32) -> zdc.u32:
            """Main task that calls a nested method."""
            await self.wait(zdc.Time.ns(3))
            result = await self.sub_task(worker_id, 10)
            return result + worker_id
    
    class Monitor:
        def __init__(self):
            self.events = []

        def enter(self, m: str, thread: Thread, time_ns: float, args: Dict[str, Any]):
            self.events.append(('enter', m, thread, time_ns, args))

        def leave(self, m: str, thread: Thread, time_ns: float, ret: Any, exc: Optional[Exception]):
            self.events.append(('leave', m, thread, time_ns, ret, exc))

    m = Monitor()

    with with_tracer(m):
        w = Worker()

    # Run two concurrent threads
    async def run_concurrent():
        task1 = asyncio.create_task(w.main_task(1))
        task2 = asyncio.create_task(w.main_task(2))
        results = await asyncio.gather(task1, task2)
        return results

    results = asyncio.run(run_concurrent())
    
    assert results == [11, 22]  # worker1: 10*1 + 1 = 11, worker2: 10*2 + 2 = 22
    
    # We should have 8 events total: 2 threads * (main_task enter/leave + sub_task enter/leave)
    assert len(m.events) == 8
    
    # Extract events by thread ID
    thread_events = {}
    for event in m.events:
        event_type, method, thread, time_ns, *rest = event
        tid = thread.tid
        if tid not in thread_events:
            thread_events[tid] = []
        thread_events[tid].append(event)
    
    # Should have exactly 2 threads
    assert len(thread_events) == 2
    
    # Each thread should have 4 events (main_task enter/leave, sub_task enter/leave)
    for tid, events in thread_events.items():
        assert len(events) == 4, f"Thread {tid} has {len(events)} events, expected 4"
        
        # Verify proper nesting: main_task.enter -> sub_task.enter -> sub_task.leave -> main_task.leave
        assert events[0][1] == 'main_task' and events[0][0] == 'enter'
        assert events[1][1] == 'sub_task' and events[1][0] == 'enter'
        assert events[2][1] == 'sub_task' and events[2][0] == 'leave'
        assert events[3][1] == 'main_task' and events[3][0] == 'leave'
        
        # Verify timestamps are monotonically increasing for this thread
        times = [e[3] for e in events]
        assert times == sorted(times), f"Thread {tid} timestamps not monotonic: {times}"
    
    # Verify that nested calls share the same tid as their parent
    for tid, events in thread_events.items():
        main_enter = events[0]
        sub_enter = events[1]
        sub_leave = events[2]
        main_leave = events[3]
        
        # All events in this thread should have the same tid
        assert main_enter[2].tid == tid
        assert sub_enter[2].tid == tid
        assert sub_leave[2].tid == tid
        assert main_leave[2].tid == tid
        
        # Nested calls should have no parent (each asyncio.Task creates a new context)
        assert main_enter[2].parent is None
        assert sub_enter[2].parent is None
        
        # Verify worker_id matches in arguments
        worker_id = main_enter[4]['worker_id']
        assert sub_enter[4]['worker_id'] == worker_id
        assert sub_enter[4]['value'] == 10

def test_deeply_nested_calls_single_thread():
    """Test that deeply nested calls maintain the same thread ID."""
    
    @zdc.dataclass
    class Nested(zdc.Component):

        async def level3(self, x: zdc.u32) -> zdc.u32:
            await self.wait(zdc.Time.ns(1))
            return x + 3
        
        async def level2(self, x: zdc.u32) -> zdc.u32:
            await self.wait(zdc.Time.ns(1))
            result = await self.level3(x + 2)
            return result
        
        async def level1(self, x: zdc.u32) -> zdc.u32:
            await self.wait(zdc.Time.ns(1))
            result = await self.level2(x + 1)
            return result
    
    class Monitor:
        def __init__(self):
            self.events = []

        def enter(self, m: str, thread: Thread, time_ns: float, args: Dict[str, Any]):
            self.events.append(('enter', m, thread, time_ns, args))

        def leave(self, m: str, thread: Thread, time_ns: float, ret: Any, exc: Optional[Exception]):
            self.events.append(('leave', m, thread, time_ns, ret, exc))

    m = Monitor()

    with with_tracer(m):
        n = Nested()

    result = asyncio.run(n.level1(10))
    
    # 10 + 1 = 11, then 11 + 2 = 13, then 13 + 3 = 16
    assert result == 16
    
    # Should have 6 events (3 levels * 2 events each)
    assert len(m.events) == 6
    
    # All events should have the same thread ID (single execution thread)
    threads = [e[2] for e in m.events]
    tids = [t.tid for t in threads]
    assert len(set(tids)) == 1, f"Expected single thread ID, got {set(tids)}"
    
    base_tid = tids[0]
    
    # Verify proper nesting structure
    assert m.events[0][0] == 'enter' and m.events[0][1] == 'level1' and m.events[0][3] == 0.0
    assert m.events[0][4] == {'x': 10}
    assert m.events[1][0] == 'enter' and m.events[1][1] == 'level2' and m.events[1][3] == 1.0
    assert m.events[1][4] == {'x': 11}
    assert m.events[2][0] == 'enter' and m.events[2][1] == 'level3' and m.events[2][3] == 2.0
    assert m.events[2][4] == {'x': 13}
    assert m.events[3][0] == 'leave' and m.events[3][1] == 'level3' and m.events[3][3] == 3.0
    assert m.events[3][4] == 16 and m.events[3][5] is None
    assert m.events[4][0] == 'leave' and m.events[4][1] == 'level2' and m.events[4][3] == 3.0
    assert m.events[4][4] == 16 and m.events[4][5] is None
    assert m.events[5][0] == 'leave' and m.events[5][1] == 'level1' and m.events[5][3] == 3.0
    assert m.events[5][4] == 16 and m.events[5][5] is None


