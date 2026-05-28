# How-to: React to SW Writes via Callbacks

Zuspec register fields can notify observers whenever software writes to them.
This is useful for hardware models that need to react to SW configuration
(side-effects, DMA kicks, interrupt clears).

---

## Synchronous callbacks

### Register-level — `reg.on_write(cb)`

Called after every *bus-side* write to the register, with the packed word
values before and after onwrite semantics are applied:

```python
regs = DMARegs()

handle = regs.CTRL.on_write(
    lambda old, new: print(f"CTRL written: {old:#010x} → {new:#010x}")
)

# … run simulation …

handle.cancel()   # deregister
```

### Field-level — `field.on_write(cb)`

Called whenever a specific field is written by SW:

```python
field = regs.CTRL._fields['START']
handle = field.on_write(lambda old, new: print(f"START: {old} → {new}"))
handle.cancel()
```

### SW-modify strobe — `field.on_swmod(cb)`

A field declared with `swmod=True` (or `singlepulse=True`) exposes a
`swmod` signal.  Use `on_swmod` for a zero-argument callback:

```python
@zdc.reg(offset=0x00)
class CTRL:
    START: zdc.u1 = zdc.reg_field(sw=zdc.SW.RW, hw=zdc.HW.R,
                                   singlepulse=True, swmod=True)

regs.CTRL._fields['START'].on_swmod(lambda: print("START pulsed by SW"))
```

You can also poll `field.swmod` (bool) after a bus write.

### HW-write callback — `field.on_hw_write(cb)`

Called whenever hardware assigns a new value to the field via `_hw_assign()`:

```python
regs.STATUS._fields['DONE'].on_hw_write(
    lambda old, new: print(f"DONE set by HW: {old} → {new}")
)
```

---

## Async waits

Use `await field.wait_any_write()` when you want a hardware task to suspend
and receive the next SW-written value:

```python
async def irq_handler(regs: DMARegs):
    while True:
        new_val = await regs.CTRL._fields['ABORT'].wait_any_write()
        if new_val:
            print("Abort requested — aborting DMA")
            regs.STATUS._fields['BUSY']._hw_assign(0)
            regs.STATUS._fields['ERROR']._hw_assign(1)
```

---

## Callbacks vs `wait_until`

| Approach | When to use |
|---|---|
| `on_write` / `on_swmod` callbacks | One-shot or persistent side-effects; logging; driving derived signals |
| `await field.wait_set()` / `wait_until` | Suspending a coroutine until a condition; cleaner control flow |
| `await field.wait_any_write()` | Hardware task that processes every SW write in sequence |

Callbacks are synchronous and execute immediately when the field is written.
`wait_until` and `wait_any_write` are async and integrate naturally with
structured concurrency (`asyncio.gather`, etc.).

---

## Example: hardware reacting to an SW start strobe

```python
import asyncio
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.base import RegisterFile


@zdc.regfile
class EngineRegs(RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x04)
    class STATUS:
        RUNNING: zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W, default=0)
        DONE:    zdc.u1 = zdc.FieldAttr.StickyBit


async def hw_model(regs: EngineRegs):
    """React to each START pulse."""
    while True:
        await regs.CTRL._fields['START'].wait_set()
        regs.STATUS._fields['RUNNING']._hw_assign(1)
        await asyncio.sleep(0.001)   # simulate work
        regs.STATUS._fields['DONE']._hw_assign(1)
        regs.STATUS._fields['RUNNING']._hw_assign(0)
```
