
import asyncio
import dataclasses as dc
import heapq
from typing import List, Tuple, Callable, Optional
from ..types import Timebase as TimebaseP, Time, TimeUnit

@dc.dataclass
class Timebase(TimebaseP):
    """Simulation timebase using synthetic time (not wallclock).
    
    Uses an event queue to track waiting coroutines and advances
    simulation time discretely.
    """
    _current_time: int = dc.field(default=0)  # Time in femtoseconds
    _event_queue: List[Tuple[int, int, asyncio.Future]] = dc.field(default_factory=list)
    _event_counter: int = dc.field(default=0)  # For stable sorting of same-time events
    _running: bool = dc.field(default=False)

    @staticmethod
    def _time_to_fs(amt: Time) -> int:
        """Convert Time to femtoseconds for internal representation."""
        if amt is None:
            return 0  # Delta time
        # Handle raw integers as nanoseconds for convenience
        if isinstance(amt, (int, float)):
            return int(amt * 10**6)  # ns to fs
        multipliers = {
            TimeUnit.S: 10**15,
            TimeUnit.MS: 10**12,
            TimeUnit.US: 10**9,
            TimeUnit.NS: 10**6,
            TimeUnit.PS: 10**3,
            TimeUnit.FS: 1,
        }
        return int(amt.amt * multipliers[amt.unit])

    async def wait(self, amt: Optional[Time] = None):
        """Suspend calling coroutine until specified simulation time elapses."""
        delay_fs = self._time_to_fs(amt)
        wake_time = self._current_time + delay_fs
        
        future = asyncio.get_event_loop().create_future()
        self._event_counter += 1
        heapq.heappush(self._event_queue, (wake_time, self._event_counter, future))
        
        await future

    def after(self, amt: Optional[Time], call: Callable):
        """Schedule 'call' to be invoked at 'amt' in the future."""
        delay_fs = self._time_to_fs(amt)
        wake_time = self._current_time + delay_fs
        
        # Create a callback entry - store the callback directly
        self._event_counter += 1
        # Use None as a marker for callback (vs Future for coroutines)
        heapq.heappush(self._event_queue, (wake_time, self._event_counter, call))

    def advance(self) -> bool:
        """Advance simulation time to the next event and wake waiters.
        
        Returns True if there are more events, False if queue is empty.
        """
        if not self._event_queue:
            return False
        
        # Get next event time
        next_time = self._event_queue[0][0]
        self._current_time = next_time
        
        # Wake all events at this time
        while self._event_queue and self._event_queue[0][0] == next_time:
            _, _, item = heapq.heappop(self._event_queue)
            
            # Check if it's a callback or a Future
            if callable(item):
                # It's a callback - invoke it
                item()
            elif hasattr(item, 'done') and not item.done():
                # It's a Future - set result
                item.set_result(None)
        
        return len(self._event_queue) > 0

    async def run_until(self, amt: Time):
        """Run simulation until specified time, then return."""
        end_time = self._current_time + self._time_to_fs(amt)
        self._running = True
        
        while self._running:
            if not self._event_queue:
                # No pending events, yield to let tasks run
                await asyncio.sleep(0)
                if not self._event_queue:
                    # Still no events, we're done
                    break
                    
            # Check if next event is beyond our end time
            if self._event_queue[0][0] > end_time:
                break
            
            # Advance time and wake waiting coroutines
            self.advance()
            
            # Yield control to let woken coroutines run
            await asyncio.sleep(0)
        
        self._current_time = end_time
        self._running = False

    def stop(self):
        """Stop the simulation loop."""
        self._running = False

    @property
    def current_time(self) -> int:
        """Current simulation time in femtoseconds."""
        return self._current_time
    
    def time(self) -> Time:
        """Returns the current time in nanoseconds."""
        return Time(TimeUnit.NS, self._current_time / 10**6)
    
