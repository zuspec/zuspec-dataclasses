"""FieldRT: per-field simulation engine with full access-type semantics."""
from __future__ import annotations

import asyncio
from typing import Callable, List, Optional, Tuple, Union

from .descriptor import FieldDescriptor
from .enums import SW, HW


class WriteHandle:
    """Returned by every ``on_*`` callback registration.

    Call :meth:`cancel` to deregister the callback.  Safe to call multiple
    times.
    """

    def __init__(self, owner: "FieldRT", key: str, cb: Callable):
        self._owner = owner
        self._key   = key
        self._cb    = cb

    def cancel(self) -> None:
        lst = self._owner._callbacks.get(self._key, [])
        try:
            lst.remove(self._cb)
        except ValueError:
            pass  # already removed — idempotent


class FieldRT:
    """Runtime simulation model for one register field.

    Instances are created by :class:`~zuspec.dataclasses.mmr.register_rt.RegisterRT`
    during register-file elaboration.  They are not constructed directly by
    user code.

    Access semantics
    ----------------
    *Bus-side (SW path)*: :meth:`write` and helpers obey ``sw``, ``onwrite``,
    and ``onread`` rules.

    *Hardware-side (HW path)*: :meth:`_hw_assign` implements the
    ``hwset`` / ``hwclr`` / full-``next`` dispatch, plus stickybit edge
    detection.

    *Wait primitives*: all ``wait_*`` methods are coroutines and must be
    awaited inside a ``@zdc.proc`` context.
    """

    def __init__(self, desc: FieldDescriptor, field_name: str):
        if desc._width is None:
            raise RuntimeError(
                f"FieldDescriptor for '{field_name}' has no width — "
                "it must be processed by @zdc.reg before instantiation."
            )
        self._desc        = desc
        self._name        = field_name
        self._width       = desc._width
        self._mask        = (1 << self._width) - 1
        self._value       = desc.default & self._mask
        self._reset_value = desc.default & self._mask

        # Events
        self._change    = asyncio.Event()
        self._any_write = asyncio.Event()

        # In-delta observability flags
        self._swmod = False
        self._swacc = False

        # Edge-detect pipeline register for stickybit
        self._prev_hw: int = 0

        # Callbacks: key → list of callables
        self._callbacks: dict[str, list] = {
            'write':    [],
            'hw_write': [],
            'change':   [],
            'swmod':    [],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _store(self, new_val: int) -> None:
        """Unconditionally store *new_val* (masked), fire events."""
        new_val &= self._mask
        old = self._value
        self._value = new_val
        # Pulse _any_write on every store call
        self._any_write.set()
        self._any_write.clear()
        if new_val != old:
            self._change.set()
            self._change.clear()
            for cb in list(self._callbacks['change']):
                cb(old, new_val)

    def _apply_onwrite(self, write_data: int, strobe_mask: int) -> int:
        """Apply onwrite semantics; return the new field value."""
        d = write_data & self._mask
        r = self._value
        ow = self._desc.onwrite
        if ow is None:
            return (r & ~strobe_mask) | (d & strobe_mask)
        elif ow == 'woset':
            return r | (d & strobe_mask)
        elif ow == 'woclr':
            return r & ~(d & strobe_mask)
        elif ow == 'wot':
            return r ^ (d & strobe_mask)
        elif ow == 'wzs':
            return r | (~d & strobe_mask & self._mask)
        elif ow == 'wzc':
            return r & (d | (~strobe_mask & self._mask))
        elif ow == 'wzt':
            return r ^ (~d & strobe_mask & self._mask)
        elif ow == 'wclr':
            return 0
        elif ow == 'wset':
            return self._mask
        return r  # unreachable

    def _bus_write_entry(self, data: int, strobe_mask: int) -> None:
        """Full bus-side write: validate SW access, apply semantics, fire events."""
        sw = self._desc.sw
        if sw == SW.RO or sw == SW.NA:
            return  # silently discard

        self._swacc = True
        old = self._value
        effective = self._apply_onwrite(data, strobe_mask)
        self._store(effective)

        if self._value != old:
            self._swmod = True
            for cb in list(self._callbacks['swmod']):
                cb()

        for cb in list(self._callbacks['write']):
            cb(old, self._value)

        # Singlepulse auto-clear — only works inside a running event loop
        if self._desc.singlepulse and self._value != 0:
            try:
                asyncio.get_running_loop().create_task(self._singlepulse_clear())
            except RuntimeError:
                pass  # no running loop; singlepulse not active in sync context

        self._swacc = False
        self._swmod = False

    def _hw_assign(self, value: int) -> None:
        """Hardware-side assignment; implements hwset/hwclr/full-next + stickybit.

        Dispatch rules:
        - hwset=True, hwclr=False: OR-accumulate; value=0 is a no-op.
        - hwset=False, hwclr=True: clear on value=0; value!=0 is a no-op.
        - hwset=True, hwclr=True:  full-drive (HW can freely set or clear).
        - neither set:             full-drive.
        """
        desc = self._desc

        # Full-drive when both or neither flag is set
        full_drive = (not desc.hwset and not desc.hwclr) or (desc.hwset and desc.hwclr)

        if not full_drive and desc.hwset:
            if value == 0:
                # hwset-only: assigning 0 is a no-op
                self._prev_hw = 0
                return
            # Stickybit edge detection
            if desc.stickybit == 'posedge':
                trigger = (not self._prev_hw) and bool(value & 1)
            elif desc.stickybit == 'negedge':
                trigger = bool(self._prev_hw) and not bool(value & 1)
            elif desc.stickybit == 'bothedge':
                trigger = bool(self._prev_hw) != bool(value & 1)
            else:
                trigger = True  # level-sensitive or no stickybit

            if trigger:
                new_val = self._value | (value & self._mask)
                old = self._value
                self._store(new_val)
                if new_val != old:
                    for cb in list(self._callbacks['hw_write']):
                        cb(old, new_val)
            self._prev_hw = int(bool(value & 1))

        elif not full_drive and desc.hwclr and value == 0:
            self._prev_hw = 0
            # stickybit field: cleared only by SW woclr write; no _store here.
            # For plain hwclr (non-stickybit) fields, clear the field.
            if not desc.stickybit and not desc.sticky:
                old = self._value
                self._store(0)
                if 0 != old:
                    for cb in list(self._callbacks['hw_write']):
                        cb(old, 0)

        else:
            # Full next-drive (neither flag, both flags, or hwclr-only with value!=0)
            old = self._value
            self._store(value & self._mask)
            if self._value != old:
                for cb in list(self._callbacks['hw_write']):
                    cb(old, self._value)

    async def _singlepulse_clear(self) -> None:
        """Auto-clear a singlepulse field after one tick."""
        await asyncio.sleep(0)  # yield to allow sampling in same delta
        self._store(0)

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    @property
    def value(self) -> int:
        """Current stored field value.  Available in all contexts."""
        return self._value

    def read(self) -> int:
        """Bus-side read; applies onread side-effect (rclr/rset) if declared."""
        sw = self._desc.sw
        if sw == SW.WO:
            return 0
        if sw == SW.NA:
            return 0
        v = self._value
        self._swacc = True
        if self._desc.onread == 'rclr':
            self._store(0)
        elif self._desc.onread == 'rset':
            self._store(self._mask)
        self._swacc = False
        return v

    def is_set(self) -> bool:
        """True if value != 0."""
        return self._value != 0

    def is_clear(self) -> bool:
        """True if value == 0."""
        return self._value == 0

    # ------------------------------------------------------------------
    # Public SW bus-side write API
    # ------------------------------------------------------------------

    def write(self, value: int) -> None:
        """Bus-side write with full onwrite semantics."""
        self._bus_write_entry(value & self._mask, self._mask)

    def set(self) -> None:
        """Bus-side write of all-ones."""
        self._bus_write_entry(self._mask, self._mask)

    def clear(self) -> None:
        """Bus-side write of all-zeros."""
        self._bus_write_entry(0, self._mask)

    def toggle(self) -> None:
        """Bus-side write XOR all-ones."""
        self._bus_write_entry(self._value ^ self._mask, self._mask)

    def set_bits(self, mask: int) -> None:
        """Bus-side OR field with mask."""
        self._bus_write_entry(self._value | (mask & self._mask), self._mask)

    def clear_bits(self, mask: int) -> None:
        """Bus-side AND field with ~mask."""
        self._bus_write_entry(self._value & ~(mask & self._mask), self._mask)

    # ------------------------------------------------------------------
    # Observability outputs (hwif_out equivalents)
    # ------------------------------------------------------------------

    @property
    def swmod(self) -> bool:
        """True during the delta of a SW-modifying write."""
        return self._swmod

    @property
    def swacc(self) -> bool:
        """True during the delta of any SW access."""
        return self._swacc

    @property
    def ored(self) -> bool:
        """OR-reduction: True if any bit is 1."""
        return self._value != 0

    @property
    def anded(self) -> bool:
        """AND-reduction: True if all bits are 1."""
        return self._value == self._mask

    @property
    def xored(self) -> bool:
        """XOR-reduction: True if an odd number of bits are 1."""
        v = self._value
        result = 0
        while v:
            result ^= v & 1
            v >>= 1
        return bool(result)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Restore field to its declared reset value."""
        self._store(self._reset_value)
        self._prev_hw = 0

    # ------------------------------------------------------------------
    # Event-driven waits (@zdc.proc only)
    # ------------------------------------------------------------------

    async def wait(self, target: int) -> None:
        """Suspend until field.value == target."""
        target &= self._mask
        while self._value != target:
            await self._wait_change()

    async def wait_set(self) -> None:
        """Suspend until field.value != 0."""
        while self._value == 0:
            await self._wait_change()

    async def wait_clear(self) -> None:
        """Suspend until field.value == 0."""
        while self._value != 0:
            await self._wait_change()

    async def wait_ne(self, value: int) -> None:
        """Suspend until field.value != value."""
        value &= self._mask
        while self._value == value:
            await self._wait_change()

    async def wait_any_write(self) -> int:
        """Suspend until any write occurs; returns new value."""
        # Use a future that resolves on the next _any_write pulse
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        original_set = self._any_write.set

        def _one_shot_set():
            original_set()
            if not fut.done():
                fut.set_result(self._value)
            self._any_write.set = original_set  # restore

        self._any_write.set = _one_shot_set  # type: ignore[method-assign]
        return await fut

    async def _wait_change(self) -> None:
        """Internal: park until _change fires."""
        ev = asyncio.Event()

        original_set = self._change.set
        def _one_shot():
            original_set()
            if not ev.is_set():
                ev.set()
        # temporarily patch; restored below
        self._change.set = _one_shot  # type: ignore[method-assign]
        try:
            await ev.wait()
        finally:
            self._change.set = original_set  # type: ignore[method-assign]

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_write(self, cb: Callable[[int, int], None]) -> WriteHandle:
        """Register a callback for every bus-side (SW) write.

        *cb* is called synchronously with ``(old_value, new_value)``
        immediately after the onwrite side-effect is applied.  A write that
        leaves the value unchanged still fires the callback.

        Returns a :class:`WriteHandle`; call ``.cancel()`` to deregister.
        """
        self._callbacks['write'].append(cb)
        return WriteHandle(self, 'write', cb)

    def on_hw_write(self, cb: Callable[[int, int], None]) -> WriteHandle:
        """Register a callback for every hardware-side write.

        *cb* is called with ``(old_value, new_value)`` after ``_hw_assign``
        updates the stored value.  Fires for ``hwset``, ``hwclr``, and
        full ``next``-drive writes.

        Returns a :class:`WriteHandle`; call ``.cancel()`` to deregister.
        """
        self._callbacks['hw_write'].append(cb)
        return WriteHandle(self, 'hw_write', cb)

    def on_change(self, cb: Callable[[int, int], None]) -> WriteHandle:
        """Register a callback whenever the stored value changes from any path.

        *cb* receives ``(old_value, new_value)``.  Only fires when the value
        actually changes; writes that leave the value unchanged do not fire.

        Returns a :class:`WriteHandle`; call ``.cancel()`` to deregister.
        """
        self._callbacks['change'].append(cb)
        return WriteHandle(self, 'change', cb)

    def on_swmod(self, cb: Callable[[], None]) -> WriteHandle:
        """Register a callback for the swmod pulse.

        *cb* is called with no arguments during the delta when a SW write
        modifies the field value.  Mirrors the ``hwif_out.<reg>.swmod``
        signal in generated RTL.

        Returns a :class:`WriteHandle`; call ``.cancel()`` to deregister.
        """
        self._callbacks['swmod'].append(cb)
        return WriteHandle(self, 'swmod', cb)
