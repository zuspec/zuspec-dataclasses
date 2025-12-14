#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""Runtime implementation of TLM Channel and interfaces."""

from __future__ import annotations
import asyncio
import dataclasses as dc
from typing import Generic, TypeVar, Optional, Tuple, Type, Any
from collections import deque

T = TypeVar('T')


@dc.dataclass
class ChannelRT(Generic[T]):
    """Runtime implementation of a TLM Channel.
    
    Provides FIFO-based communication between producer and consumer.
    The channel has separate put and get interfaces that can be bound
    to ports on different components.
    """
    _queue: deque = dc.field(default_factory=deque)
    _element_type: Optional[Type] = dc.field(default=None)
    _max_size: int = dc.field(default=0)  # 0 = unlimited
    _put_waiters: list = dc.field(default_factory=list)
    _get_waiters: list = dc.field(default_factory=list)
    
    def __post_init__(self):
        # Create the put and get interface objects
        self.put = PutIFRT(self)
        self.get = GetIFRT(self)
    
    def _notify_get_waiters(self):
        """Wake up any tasks waiting to get."""
        while self._get_waiters and self._queue:
            waiter = self._get_waiters.pop(0)
            if not waiter.done():
                waiter.set_result(None)
    
    def _notify_put_waiters(self):
        """Wake up any tasks waiting to put (if channel has max size)."""
        while self._put_waiters:
            if self._max_size == 0 or len(self._queue) < self._max_size:
                waiter = self._put_waiters.pop(0)
                if not waiter.done():
                    waiter.set_result(None)
            else:
                break


@dc.dataclass
class GetIFRT(Generic[T]):
    """Runtime implementation of GetIF - the consumer side of a channel."""
    _channel: ChannelRT = dc.field()
    
    async def get(self) -> T:
        """Get an item from the channel. Blocks if channel is empty."""
        while not self._channel._queue:
            # Wait for data to be available
            loop = asyncio.get_event_loop()
            waiter = loop.create_future()
            self._channel._get_waiters.append(waiter)
            try:
                await waiter
            except asyncio.CancelledError:
                self._channel._get_waiters.remove(waiter)
                raise
        
        item = self._channel._queue.popleft()
        self._channel._notify_put_waiters()
        return item
    
    def try_get(self) -> Tuple[bool, T]:
        """Try to get an item without blocking.
        
        Returns:
            Tuple of (success, item). If success is False, item is None.
        """
        if self._channel._queue:
            item = self._channel._queue.popleft()
            self._channel._notify_put_waiters()
            return (True, item)
        return (False, None)
    
    def can_get(self) -> bool:
        """Check if there's data available to get."""
        return len(self._channel._queue) > 0


@dc.dataclass
class PutIFRT(Generic[T]):
    """Runtime implementation of PutIF - the producer side of a channel."""
    _channel: ChannelRT = dc.field()
    
    async def put(self, item: T) -> None:
        """Put an item into the channel. Blocks if channel is full (when max_size > 0)."""
        # If max_size is set, wait until there's room
        if self._channel._max_size > 0:
            while len(self._channel._queue) >= self._channel._max_size:
                loop = asyncio.get_event_loop()
                waiter = loop.create_future()
                self._channel._put_waiters.append(waiter)
                try:
                    await waiter
                except asyncio.CancelledError:
                    self._channel._put_waiters.remove(waiter)
                    raise
        
        self._channel._queue.append(item)
        self._channel._notify_get_waiters()
    
    def try_put(self, item: T) -> bool:
        """Try to put an item without blocking.
        
        Returns:
            True if item was added, False if channel is full.
        """
        if self._channel._max_size > 0 and len(self._channel._queue) >= self._channel._max_size:
            return False
        
        self._channel._queue.append(item)
        self._channel._notify_get_waiters()
        return True
    
    def can_put(self) -> bool:
        """Check if there's room to put data."""
        if self._channel._max_size == 0:
            return True
        return len(self._channel._queue) < self._channel._max_size
