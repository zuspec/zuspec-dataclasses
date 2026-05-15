# How-to: Declare a Register File

This guide shows how to describe hardware registers using Zuspec's Python
register model.  The running example is a DMA copy engine.

---

## The two declaration forms

### Form 1 — structured inner classes (recommended)

Use `@zdc.reg` inner classes when you need to set per-field properties such
as SW/HW access policies, sticky bits, or pulse semantics.

```python
import zuspec.dataclasses as zdc

@zdc.regfile
class DMARegs(zdc.RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse      # singlepulse — self-clears
        ABORT: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY:  zdc.u1 = zdc.reg_field(
            sw=zdc.SW.RO, hw=zdc.HW.W, hwset=True, hwclr=True, default=0)
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit  # set by HW, cleared by SW write-1
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit

    @zdc.reg(offset=0x08)
    class IRQ_EN:
        DONE_EN:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)
        ERROR_EN: zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)
```

### Form 2 — all-RW fields with no extra properties

When every field is simple read-write storage you can omit `zdc.reg_field()`:

```python
@zdc.regfile
class ConfigRegs(zdc.RegisterFile):

    @zdc.reg(offset=0x00)
    class THRESHOLD:
        VALUE: zdc.u8 = zdc.reg_field(default=0x10)   # 8-bit counter threshold

    @zdc.reg(offset=0x04)
    class PERIOD:
        COUNT: zdc.u16 = zdc.reg_field(default=1000)
```

---

## Key decorators and functions

### `@zdc.regfile`

Marks the class as an MMR register file so that synthesis tools and
SW emitters can discover it.

```python
@zdc.regfile
class MyRegs(zdc.RegisterFile):
    ...
```

### `@zdc.reg(offset, width=32)`

Declares one register.  `offset` is the byte offset within the register file.
`width` defaults to 32.

```python
@zdc.reg(offset=0x10)
class ADDR:
    VALUE: zdc.u32 = zdc.reg_field()
```

### `zdc.reg_field(...)` — full control

```python
zdc.reg_field(
    sw=zdc.SW.RW,      # software access policy
    hw=zdc.HW.R,       # hardware access policy
    lsb=0,             # bit position (auto-packed if omitted)
    default=0,         # reset value
    onwrite='woclr',   # write side-effect ('woclr', 'woset', …)
    onread='rclr',     # read side-effect ('rclr', 'rset', …)
    stickybit=False,   # hardware OR-set; SW clears via woclr
    hwset=False,       # hwif_in provides a set strobe
    hwclr=False,       # hwif_in provides a clear strobe
    singlepulse=False, # SW-written 1 auto-clears next cycle
    swmod=False,       # hwif_out carries a SW-modify strobe
)
```

Field width comes from the type annotation (`zdc.u1` … `zdc.u32`).

### `zdc.FieldAttr` presets

| Preset | Meaning |
|---|---|
| `zdc.FieldAttr.Pulse` | SW writes 1 → self-clears next cycle; `sw=RW, hw=R, singlepulse=True` |
| `zdc.FieldAttr.StickyBit` | HW OR-sets; SW write-1 clears; `sw=RW, hw=W, stickybit=True, onwrite='woclr'` |
| `zdc.FieldAttr.StatusRO` | HW drives; SW reads only; `sw=RO, hw=W` |
| `zdc.FieldAttr.HwClearable` | HW can set/clear via hwset/hwclr strobes |

### SW and HW access policies

```python
# Software side
zdc.SW.RW   # read-write
zdc.SW.RO   # read-only
zdc.SW.WO   # write-only
zdc.SW.NA   # no software access

# Hardware side
zdc.HW.R    # hardware reads the SW-written value
zdc.HW.W    # hardware drives the field value
zdc.HW.RW   # hardware reads and writes
zdc.HW.NA   # no hardware access
```

---

## Auto bit-packing

Fields are packed from bit 0 upward in declaration order if `lsb` is omitted:

```python
@zdc.reg(offset=0x00)
class FLAGS:
    A: zdc.u1 = zdc.reg_field()   # bits [0:0]
    B: zdc.u4 = zdc.reg_field()   # bits [4:1]
    C: zdc.u3 = zdc.reg_field()   # bits [7:5]
```

You can mix explicit and auto-packed fields; explicit `lsb` is used as-is.

---

## Instantiating a register file

```python
regs = DMARegs()          # create a simulation instance
regs.CTRL._fields['START'].write(1)   # write START field
print(regs.STATUS.BUSY)   # read BUSY attribute (live value)
```

See [read_write_registers.md](read_write_registers.md) for the full access API.
