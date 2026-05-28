# How-to: Wait for a Register Condition

Zuspec provides several async primitives for suspending a coroutine until a
hardware register reaches a desired state.  All primitives require an asyncio
event loop (they are safe to call from `@zdc.proc` coroutines or plain
`asyncio` tasks).

---

## Field-level waits

The simplest form targets a single field:

```python
regs = DMARegs()

# Wait until a field equals 1
await regs.STATUS._fields['BUSY'].wait_set()

# Wait until a field equals 0
await regs.STATUS._fields['BUSY'].wait_clear()

# Wait until a field equals a specific value
await regs.STATUS._fields['ERR_CODE'].wait(3)

# Wait until a field is not a specific value
await regs.STATUS._fields['STATE'].wait_ne(0)
```

| Method | Suspends until |
|---|---|
| `await field.wait_set()` | `field.value == 1` |
| `await field.wait_clear()` | `field.value == 0` |
| `await field.wait(v)` | `field.value == v` |
| `await field.wait_ne(v)` | `field.value != v` |
| `await field.wait_any_write()` | Any SW write to this field (returns new value) |

---

## Single-register predicate

When the condition spans multiple fields within one register use
`register.wait_until()`:

```python
# Wait for DONE or ERROR to be set
await regs.STATUS.wait_until(lambda s: s.DONE == 1 or s.ERROR == 1)
```

The lambda receives the live register object (not a snapshot).  Attribute
access on it returns the current field value.

---

## Multi-register predicate

Use `zdc.wait_until()` (or `from zuspec.dataclasses.mmr.wait import wait_until`)
when the condition involves fields from two or more registers:

```python
from zuspec.dataclasses.mmr.wait import wait_until

# Wait until START is written AND hardware is not busy
await wait_until(
    regs.CTRL,
    regs.STATUS,
    lambda ctrl, status: ctrl.START == 1 and status.BUSY == 0,
)
```

Arguments are `(reg1, reg2, …, predicate)`.  The predicate receives the same
register objects in order.

---

## Polling pattern for multi-reg conditions

If you need to poll a condition that does not map cleanly to a predicate you
can combine `wait_until` with a flag:

```python
async def wait_for_idle(regs: DMARegs) -> None:
    """Wait until both CTRL and STATUS indicate idle."""
    while True:
        await regs.STATUS.wait_until(lambda s: s.BUSY == 0)
        # Re-check CTRL to confirm START did not fire again
        if regs.CTRL._fields['START'].value == 0:
            return
```

---

## Notes

- All wait primitives are **level-triggered**, not edge-triggered.  If the
  condition is already true when `await` is reached, the coroutine returns
  immediately without suspending.
- Cancellation is safe: the change listener is cleaned up in a `finally` block.
- Do not call these from synchronous code; they require an active event loop.
