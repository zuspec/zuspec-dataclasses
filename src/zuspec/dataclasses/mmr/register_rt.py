"""RegisterRT: per-register simulation engine with packed-struct access."""
from __future__ import annotations

import asyncio
from typing import Callable, Dict, List, Optional

from .descriptor import FieldDescriptor
from .field_rt import FieldRT, WriteHandle


class RegisterValue:
    """Mutable snapshot of a register's field values.

    Created by :meth:`RegisterRT.read` and consumed by
    :meth:`RegisterRT.write`.  Supports ``_replace(**kwargs)`` for
    immutable-style updates::

        s = self.regs.STATUS.read()
        s2 = s._replace(DONE=1)
        self.regs.STATUS.write(s2)

    or mutate in-place::

        s = self.regs.STATUS.read()
        s.DONE = 1
        self.regs.STATUS.write(s)
    """

    def __init__(self, field_names: List[str], values: Dict[str, int],
                 descriptors: Dict[str, FieldDescriptor]):
        object.__setattr__(self, '_field_names', field_names)
        object.__setattr__(self, '_values', dict(values))
        object.__setattr__(self, '_dirty', set())
        object.__setattr__(self, '_descriptors', descriptors)

    def __getattr__(self, name: str) -> int:
        values = object.__getattribute__(self, '_values')
        if name in values:
            return values[name]
        raise AttributeError(f"No field '{name}' in RegisterValue")

    def __setattr__(self, name: str, value: int) -> None:
        values = object.__getattribute__(self, '_values')
        if name in values:
            values[name] = value
            object.__getattribute__(self, '_dirty').add(name)
        else:
            raise AttributeError(f"No field '{name}' in RegisterValue")

    def _replace(self, **kwargs) -> "RegisterValue":
        """Return a new snapshot with the named fields replaced."""
        values = dict(object.__getattribute__(self, '_values'))
        dirty  = set(object.__getattribute__(self, '_dirty'))
        field_names = object.__getattribute__(self, '_field_names')
        descs  = object.__getattribute__(self, '_descriptors')
        for k, v in kwargs.items():
            if k not in values:
                raise AttributeError(f"No field '{k}' in RegisterValue")
            values[k] = v
            dirty.add(k)
        rv = RegisterValue(field_names, values, descs)
        object.__setattr__(rv, '_dirty', dirty)
        return rv

    def __repr__(self) -> str:
        values = object.__getattribute__(self, '_values')
        parts = ', '.join(f"{k}={v}" for k, v in values.items())
        return f"RegisterValue({parts})"


class RegisterRT:
    """Runtime simulation model for one register.

    Contains an ordered collection of :class:`~.field_rt.FieldRT` instances
    and provides:

    * Bus-side ``read()`` / ``write()`` (integer or :class:`RegisterValue`)
    * HW-side direct attribute access (``reg.FIELD = v`` → ``_hw_assign``)
    * ``wait_until(pred)`` for ``@zdc.proc`` contexts
    * ``intr`` property (OR of all stickybit/sticky fields)
    * Register-level ``on_write`` callback
    """

    def __init__(self, reg_name: str, offset: int, width: int = 32):
        self._name    = reg_name
        self._offset  = offset
        self._width   = width
        self._fields: Dict[str, FieldRT]  = {}     # ordered (Python 3.7+)
        self._field_lsbs: Dict[str, int]  = {}
        self._change  = asyncio.Event()
        self._write_callbacks: list = []

    # ------------------------------------------------------------------
    # Field registration (called during elaboration)
    # ------------------------------------------------------------------

    def _add_field(self, name: str, field: FieldRT, lsb: int) -> None:
        self._fields[name] = field
        self._field_lsbs[name] = lsb
        # Propagate field changes to register change event
        field.on_change(lambda old, new: self._fire_change())

    def _fire_change(self) -> None:
        self._change.set()
        self._change.clear()

    # ------------------------------------------------------------------
    # Bus-side API (SW path)
    # ------------------------------------------------------------------

    def bus_read(self) -> int:
        """Bus-side read: pack all fields into a register word; apply onread."""
        word = 0
        for name, field in self._fields.items():
            lsb = self._field_lsbs[name]
            word |= (field.read() & field._mask) << lsb
        return word

    def bus_write(self, value: int, strobe: int = 0xF) -> None:
        """Bus-side write: unpack word and dispatch each field with strobe.

        *strobe* is a byte-enable mask (1 bit per byte, AXI WSTRB style).
        """
        old_word = self._pack_raw()
        bytes_per_word = self._width // 8
        for name, field in self._fields.items():
            lsb = self._field_lsbs[name]
            # Build a per-field strobe mask based on which bytes of the
            # register word the field occupies.
            field_strobe = self._field_strobe(lsb, field._width, strobe, bytes_per_word)
            if field_strobe == 0:
                continue
            field_data = (value >> lsb) & field._mask
            field._bus_write_entry(field_data, field_strobe & field._mask)

        new_word = self._pack_raw()
        for cb in list(self._write_callbacks):
            cb(old_word, new_word)

    @staticmethod
    def _field_strobe(lsb: int, width: int, reg_strobe: int, bytes_per_word: int) -> int:
        """Return a bit mask (field-width bits) active where strobe covers the field."""
        # For each bit in the field, check if its byte is enabled
        result = 0
        for bit in range(width):
            byte_idx = (lsb + bit) // 8
            if byte_idx < bytes_per_word and (reg_strobe >> byte_idx) & 1:
                result |= (1 << bit)
        return result

    def _pack_raw(self) -> int:
        """Pack current field values into integer without side-effects."""
        word = 0
        for name, field in self._fields.items():
            lsb = self._field_lsbs[name]
            word |= (field._value & field._mask) << lsb
        return word

    # ------------------------------------------------------------------
    # @zdc.proc snapshot API
    # ------------------------------------------------------------------

    def read(self) -> RegisterValue:
        """Return a mutable value snapshot of this register.

        The snapshot is independent of the live register; modifying it does
        not affect the register until :meth:`write` is called.
        """
        values = {name: field.read() for name, field in self._fields.items()}
        descs  = {name: field._desc for name, field in self._fields.items()}
        return RegisterValue(list(self._fields.keys()), values, descs)

    def write(self, snapshot: RegisterValue, strobe: int = 0xF) -> None:
        """Commit a value snapshot to the register.

        For each *dirty* field in the snapshot the appropriate path is chosen:
        - ``hwset``/``hwclr`` fields use :meth:`~field_rt.FieldRT._hw_assign`.
        - All other HW-writable fields use :meth:`~field_rt.FieldRT._hw_assign`.
        - Fields not dirty are left unchanged.

        This mirrors the ``@zdc.proc`` pattern of read-modify-write.
        """
        dirty = object.__getattribute__(snapshot, '_dirty')
        values = object.__getattribute__(snapshot, '_values')
        for name, field in self._fields.items():
            if name in dirty:
                field._hw_assign(values[name])

    # ------------------------------------------------------------------
    # Direct HW attribute access (for @zdc.comb / @zdc.sync)
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        # Only intercept field names; everything else uses normal lookup
        fields = object.__getattribute__(self, '_fields')
        if name in fields:
            return fields[name]._value
        raise AttributeError(f"RegisterRT '{self._name}' has no field '{name}'")

    def __setattr__(self, name: str, value) -> None:
        # During __init__ _fields may not yet exist
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        try:
            fields = object.__getattribute__(self, '_fields')
        except AttributeError:
            object.__setattr__(self, name, value)
            return
        if name in fields:
            fields[name]._hw_assign(value)
        else:
            object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    # Properties and register-level helpers
    # ------------------------------------------------------------------

    @property
    def intr(self) -> bool:
        """OR of all stickybit / sticky fields (mirrors hwif_out.<reg>.intr)."""
        for field in self._fields.values():
            if (field._desc.stickybit or field._desc.sticky) and field._value:
                return True
        return False

    def reset(self) -> None:
        """Restore all fields to their declared reset values."""
        for field in self._fields.values():
            field.reset()

    def on_write(self, cb: Callable[[int, int], None]) -> WriteHandle:
        """Register a callback for every bus-side write to this register.

        *cb* is called with ``(old_word, new_word)`` as packed integers after
        all field onwrite semantics have been applied.  Called by
        :meth:`bus_write` only — direct :meth:`write` (snapshot) calls do not
        fire this callback.

        Returns a handle with a ``.cancel()`` method to deregister.

        Example::

            handle = regs.CTRL.on_write(lambda old, new: print(f"CTRL: {old:#x} → {new:#x}"))
            # … later …
            handle.cancel()
        """
        self._write_callbacks.append(cb)
        # Return a handle-like object (uses the first field as owner for simplicity)
        class _RegWriteHandle:
            def cancel(self_, ) -> None:  # noqa: N805
                try:
                    self._write_callbacks.remove(cb)
                except ValueError:
                    pass
        return _RegWriteHandle()  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Async wait (@zdc.proc only)
    # ------------------------------------------------------------------

    async def wait_until(self, pred: Callable[["RegisterRT"], bool]) -> None:
        """Suspend until pred(self) is True.

        Re-evaluated on every field change.  Use for multi-field predicates
        within one register::

            await self.regs.CTRL.wait_until(lambda r: r.START == 1)
        """
        while not pred(self):
            ev = asyncio.Event()
            original_set = self._change.set

            def _one_shot():
                original_set()
                if not ev.is_set():
                    ev.set()

            self._change.set = _one_shot  # type: ignore[method-assign]
            try:
                await ev.wait()
            finally:
                self._change.set = original_set  # type: ignore[method-assign]
