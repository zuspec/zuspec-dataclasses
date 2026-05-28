# Verification Constructs (`zuspec.dataclasses`)

Covers randomization, constraints, coverage, action-based scenarios, and
contract assertions.  
See [core.md](core.md) for `Component` and field basics.

---

## Randomization

`zdc.randomize(obj)` solves constraints and populates `rand`-annotated
fields. `zdc.randomize_with(obj, lambda ...)` adds inline extra constraints.

| Annotation | Semantics |
|---|---|
| `zdc.rand` | Field participates in randomization |
| `zdc.randc` | Cyclic randomization (SV `randc` semantics) |

---

## Constraints

Declared as methods decorated with `@zdc.constraint`:

```python
@zdc.dataclass
class Packet(zdc.Struct):
    length: zdc.u16 = zdc.rand()

    @zdc.constraint
    def c_length(self):
        self.length >= 64
        self.length <= 1500
```

Helper functions:

| Function | Purpose |
|---|---|
| `zdc.implies(cond, body)` | Conditional constraint |
| `zdc.dist(field, weights)` | Weighted distribution |
| `zdc.unique(*fields)` | All values distinct |
| `zdc.sum(iterable)` | Sum expression |
| `zdc.ascending(*fields)` | Ordered constraint |
| `zdc.solve_order(*fields)` | Solver ordering hint |

See `docs/constraints.rst` for the full reference.

---

## Functional Coverage

```python
@zdc.dataclass
class PktCov(zdc.Covergroup):
    @zdc.coverpoint
    def cp_length(self): return self.pkt.length

    @zdc.cross
    def cx_len_proto(self): return [self.cp_length, self.cp_proto]
```

Bin filtering: `zdc.binsof`, `zdc.cross_bins`, `zdc.cross_ignore`,
`zdc.cross_illegal`.

---

## Action-Based Test Scenarios

### `zdc.Action`

Atomic test step. Actions can declare `rand` fields, constraints, and
pre/post conditions.

```python
@zdc.dataclass
class WriteAction(zdc.Action):
    addr: zdc.u32 = zdc.rand()
    data: zdc.u32 = zdc.rand()
```

### Activity DSL

Compose actions into activity graphs:

| DSL call | Meaning |
|---|---|
| `zdc.do(ActionClass)` | Execute one action |
| `zdc.sequence(...)` | Run actions in order |
| `zdc.parallel(...)` | Run actions concurrently |
| `zdc.select(...)` | Non-deterministic choice |
| `zdc.replicate(n, ...)` | Repeat N times |

### `zdc.ScenarioRunner` / `zdc.run_action`

Top-level entry points for executing action-based scenarios.
Use `run_action_sync` from a non-async caller.

---

## Contract Assertions

`@zdc.requires` / `@zdc.ensures` express pre- and post-conditions on
component methods. Violations raise `zdc.ContractViolation`.

```python
@zdc.requires(lambda self, addr: addr < self.size)
@zdc.ensures(lambda self, result: result is not None)
async def read(self, addr: zdc.u32) -> zdc.u32: ...
```
