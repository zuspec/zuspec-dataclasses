# How-to: Interrupt-Pending Registers (Stickybit Fields)

Interrupt-status registers follow a "no-loss" semantic: hardware can set
a bit at any time, and software reads / clears it independently.  Zuspec
models this with the `stickybit` field type.

---

## Declaring an interrupt-status register

```python
import zuspec.dataclasses as zdc

@zdc.regfile
class DMARegs(zdc.RegisterFile):

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY:  zdc.u1 = zdc.reg_field(
            sw=zdc.SW.RO, hw=zdc.HW.W, hwset=True, hwclr=True, default=0)
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit   # shorthand for stickybit
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit
```

`zdc.FieldAttr.StickyBit` is equivalent to:

```python
zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.W, stickybit=True, onwrite='woclr')
```

---

## How stickybit works

| Event | Effect |
|---|---|
| `field._hw_assign(1)` | Field is OR-set (latches 1; can never be cleared by HW directly) |
| `field._hw_assign(0)` | No effect — hardware cannot clear a stickybit |
| `field.write(1)` (SW) | Write-1-to-clear (woclr): field is cleared to 0 |
| `field.write(0)` (SW) | No effect |
| `field.read()` | Returns current latched value |

This guarantees a **no-loss** property: if hardware asserts the bit between
two polling reads, the bit stays set until software explicitly clears it.

---

## `reg.intr` — OR of all set sticky bits

A register that contains at least one stickybit field exposes an `intr`
property:

```python
if regs.STATUS.intr:
    print("Interrupt pending!")
```

`intr` is the logical OR of all stickybit / sticky fields.  It mirrors
`hwif_out.<reg>.intr` in the generated RTL.

---

## Typical software ISR pattern

```python
async def interrupt_service_routine(regs: DMARegs):
    # Wait for any interrupt
    await regs.STATUS.wait_until(lambda s: s.DONE == 1 or s.ERROR == 1)

    done  = regs.STATUS._fields['DONE'].value
    error = regs.STATUS._fields['ERROR'].value

    # Handle first, then clear to avoid losing a simultaneous new interrupt
    if done:
        handle_done()
    if error:
        handle_error()

    # Clear the sticky bits (write-1-to-clear)
    if done:
        regs.STATUS._fields['DONE'].write(1)
    if error:
        regs.STATUS._fields['ERROR'].write(1)
```

> **Clear-after-handle**: always read and process the interrupt bits *before*
> clearing them.  A new HW event that arrives during processing will re-set
> the bit after the clear, so it will be seen on the next ISR invocation.

---

## Hardware setting a stickybit

From a hardware model, use `_hw_assign(1)`:

```python
async def dma_engine(regs: DMARegs):
    await regs.CTRL._fields['START'].wait_set()
    regs.STATUS._fields['BUSY']._hw_assign(1)
    await do_transfer()
    # Notify SW: set DONE interrupt
    regs.STATUS._fields['DONE']._hw_assign(1)
    regs.STATUS._fields['BUSY']._hw_assign(0)
```

---

## Multiple interrupt sources

Use an interrupt-enable register alongside the status register:

```python
@zdc.regfile
class IRQRegs(zdc.RegisterFile):

    @zdc.reg(offset=0x00)
    class IRQ_EN:
        DONE_EN:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)
        ERROR_EN: zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R, default=0)

    @zdc.reg(offset=0x04)
    class IRQ_STATUS:
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit


async def masked_isr(regs: IRQRegs):
    await regs.IRQ_STATUS.wait_until(
        lambda s: (s.DONE and regs.IRQ_EN._fields['DONE_EN'].value) or
                  (s.ERROR and regs.IRQ_EN._fields['ERROR_EN'].value)
    )
    # … handle and clear …
```
