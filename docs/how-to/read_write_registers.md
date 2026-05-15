# How-to: Read and Write Registers in `@zdc.proc`

This guide covers the two read/write styles available inside `@zdc.proc`
coroutines (and plain asyncio code).

---

## Style 1 — Snapshot (read-modify-write)

The snapshot style is the closest to real hardware software:

```python
import zuspec.dataclasses as zdc

@zdc.regfile
class DMARegs(zdc.RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse
        ABORT: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x08)
    class IRQ_EN:
        DONE_EN:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)
        ERROR_EN: zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)


async def configure(regs: DMARegs):
    # Read a snapshot — independent copy, does not affect the live register
    snap = regs.IRQ_EN.read()

    # Modify fields on the snapshot
    snap.DONE_EN  = 1
    snap.ERROR_EN = 1

    # Commit only the dirty fields back
    regs.IRQ_EN.write(snap)
```

`RegisterValue.write()` only commits fields that were actually assigned on the
snapshot.  Unassigned fields are left unchanged in the live register.

---

## Style 2 — Direct field access

For single-field writes the snapshot is unnecessary:

```python
async def start_dma(regs: DMARegs):
    regs.CTRL._fields['START'].write(1)   # singlepulse — self-clears next cycle
```

Read the current value with `.read()` or the `.value` property:

```python
busy = regs.STATUS._fields['BUSY'].read()   # int
busy = regs.STATUS._fields['BUSY'].value    # same
```

---

## Hardware-side writes

From a hardware model (inside `@zdc.comb`, `@zdc.sync`, or an async HW task)
use `_hw_assign()` instead of `write()`.  This bypasses SW-side semantics
(onwrite callbacks, singlepulse, woclr) and goes straight to the storage:

```python
async def hw_engine(regs: DMARegs):
    regs.STATUS._fields['BUSY']._hw_assign(1)
    # … perform work …
    regs.STATUS._fields['BUSY']._hw_assign(0)
    regs.STATUS._fields['DONE']._hw_assign(1)   # sets stickybit
```

You can also use attribute assignment on the register directly:

```python
regs.STATUS.BUSY = 1   # equivalent to _hw_assign(1)
```

---

## Resetting a register

```python
regs.CTRL.reset()   # restore all fields to their declared default values
```

---

## Full copy-engine example

```python
import asyncio
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.base import RegisterFile
from zuspec.dataclasses.mmr.wait import wait_until


@zdc.regfile
class DMARegs(RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse
        ABORT: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W,
                                       hwset=True, hwclr=True, default=0)
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit


async def software_driver(regs: DMARegs) -> bool:
    """Start a DMA transfer and return True on success."""
    regs.CTRL._fields['START'].write(1)
    await wait_until(regs.STATUS, lambda s: s.DONE == 1 or s.ERROR == 1)
    done  = regs.STATUS._fields['DONE'].value
    error = regs.STATUS._fields['ERROR'].value
    # Clear sticky bits (write-1-to-clear)
    regs.STATUS._fields['DONE'].write(1)
    regs.STATUS._fields['ERROR'].write(1)
    return done == 1 and error == 0


async def hardware_engine(regs: DMARegs):
    """Simulate the DMA hardware."""
    await regs.CTRL._fields['START'].wait_set()
    regs.STATUS._fields['BUSY']._hw_assign(1)
    await asyncio.sleep(0)   # simulate transfer latency
    regs.STATUS._fields['DONE']._hw_assign(1)
    regs.STATUS._fields['BUSY']._hw_assign(0)


async def main():
    regs  = DMARegs()
    ok, _ = await asyncio.gather(software_driver(regs), hardware_engine(regs))
    assert ok

asyncio.run(main())
```
