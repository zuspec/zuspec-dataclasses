# Registers and Memory Maps

Zuspec provides a first-class register model that spans all abstraction levels:
simulation, RTL lowering, and SW artefact generation.  The model is declared
entirely in Python and maps directly to the SystemRDL vocabulary.

---

## Quick start

```python
import zuspec.dataclasses as zdc

@zdc.regfile
class DMARegs(zdc.RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse     # self-clearing start strobe
        ABORT: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W, hwset=True, hwclr=True)
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit
```

---

## Core decorators

### `@zdc.regfile`

Marks a `zdc.RegisterFile` subclass as an MMR register file.

```python
@zdc.regfile
class MyRegs(zdc.RegisterFile):
    ...
```

After decoration the class carries:

| Attribute | Contents |
|---|---|
| `cls.__zdc_regfile__` | `True` (marker flag) |
| `cls._mmr_reg_classes` | `[(attr_name, inner_cls), ...]` ordered list of registers |

### `@zdc.reg(offset, width=32)`

Declares one register as an inner class.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `offset` | `int` | required | Byte offset within the register file |
| `width` | `int` | `32` | Register width in bits |

After decoration the inner class carries:

| Attribute | Contents |
|---|---|
| `_mmr_offset` | Byte offset |
| `_mmr_width` | Register width |
| `_mmr_fields` | `[(name, FieldDescriptor), ...]` ordered list of fields |

---

## Field declarations

### `zdc.reg_field(...)` — full control

```python
EN: zdc.u1 = zdc.reg_field(
    sw=zdc.SW.RW,        # software access: RW / RO / WO / NA
    hw=zdc.HW.R,         # hardware access: R / W / RW / NA
    lsb=0,               # bit position (auto-packed if omitted)
    default=0,           # reset value
    onwrite='woclr',     # 'woclr' | 'woset' | 'wot' | 'wzc' | 'wzs' | 'wzt' | 'rsvd'
    onread='rclr',       # 'rclr' | 'rset' | 'ruser'
    stickybit=False,     # hardware OR-set; SW clears via woclr
    hwset=False,         # hwif_in provides a set strobe
    hwclr=False,         # hwif_in provides a clear strobe
    we=False,            # hwif_in provides a write-enable
    wel=False,           # hwif_in provides a write-enable-low
    singlepulse=False,   # SW-written 1 auto-clears next cycle
    swmod=False,         # hwif_out carries a SW-modify strobe
    precedence='sw',     # 'sw' | 'hw' — who wins simultaneous write
)
```

Field width comes from the type annotation (`zdc.u1` ... `zdc.u32`).

### `zdc.FieldAttr` — preset shortcuts

| Preset | Equivalent `reg_field()` |
|---|---|
| `zdc.FieldAttr.Pulse` | `sw=RW, hw=R, singlepulse=True` |
| `zdc.FieldAttr.StickyBit` | `sw=RW, hw=W, stickybit=True, onwrite='woclr'` |
| `zdc.FieldAttr.StatusRO` | `sw=RO, hw=W` |
| `zdc.FieldAttr.HwClearable` | `sw=RO, hw=W, hwset=True, hwclr=True` |

### SW and HW access enums

```python
zdc.SW.RW   # software can read and write
zdc.SW.RO   # software can only read
zdc.SW.WO   # software can only write
zdc.SW.NA   # software has no access

zdc.HW.R    # hardware can only read the SW-written value
zdc.HW.W    # hardware can write (drives the field value)
zdc.HW.RW   # hardware can read and write
zdc.HW.NA   # hardware has no access
```

---

## Runtime API

```python
regs = DMARegs()   # create a simulation instance
```

### Register-level access

```python
snap = regs.CTRL.read()      # -> RegisterValue snapshot
snap.START = 1               # dirty a field
regs.CTRL.write(snap)        # commit dirty fields only

regs.CTRL._fields['START'].write(1)   # direct field write
```

### Field-level access

```python
field = regs.STATUS._fields['BUSY']

field.read()           # -> current int value
field.write(1)         # SW write (respects onwrite semantics)
field._hw_assign(1)    # HW write (bypasses SW path)
field.value            # property: live int value
```

### Async waits (`@zdc.proc` / asyncio)

```python
await regs.STATUS._fields['DONE'].wait_set()    # wait for field == 1
await regs.STATUS._fields['BUSY'].wait_clear()  # wait for field == 0
await regs.STATUS._fields['ERR'].wait(2)        # wait for field == 2

await regs.STATUS.wait_until(lambda s: s.DONE == 1 or s.ERROR == 1)

from zuspec.dataclasses.mmr.wait import wait_until
await wait_until(regs.CTRL, regs.STATUS,
    lambda ctrl, status: ctrl.START == 1 and status.BUSY == 0)
```

### Change callbacks (synchronous)

```python
handle = regs.CTRL.on_write(lambda old, new: ...)
handle.cancel()

field.on_swmod(lambda: ...)
field.on_hw_write(lambda old, new: ...)
```

### Register-level helpers

```python
regs.STATUS.intr   # True if any stickybit field is non-zero
regs.CTRL.reset()  # restore all fields to reset values
```

---

## How-to guides

| Goal | Guide |
|---|---|
| Declare a register file | [how-to/declare_register_file.md](how-to/declare_register_file.md) |
| Read and write registers in `@zdc.proc` | [how-to/read_write_registers.md](how-to/read_write_registers.md) |
| Wait for a register condition | [how-to/wait_for_register_condition.md](how-to/wait_for_register_condition.md) |
| React to SW writes | [how-to/react_to_sw_writes.md](how-to/react_to_sw_writes.md) |
| Interrupt pending registers (stickybit) | [how-to/interrupt_pending_registers.md](how-to/interrupt_pending_registers.md) |
| Generate RTL from a register file | [how-to/generate_rtl.md](how-to/generate_rtl.md) |
| Generate SW artefacts (C header / Python driver) | [how-to/generate_sw_artefacts.md](how-to/generate_sw_artefacts.md) |

---

See also: `design/abstract-mmr.md` for the formal specification and RTL
lowering semantics.
