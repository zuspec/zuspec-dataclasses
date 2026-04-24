# Behavioral Modeling Constructs (`zuspec.dataclasses`)

Covers BFM / behavioral simulation constructs.  
See [core.md](core.md) for `Component`, ports, and binding basics.

---

## `zdc.IfProtocol`

Base class for interface protocol definitions. Subclass it and declare
`async` methods to define a typed, synthesizer-aware interface.

```python
class BusIF(zdc.IfProtocol, max_outstanding=4):
    async def read(self, addr: zdc.u32) -> zdc.u32: ...
    async def write(self, addr: zdc.u32, data: zdc.u32) -> None: ...
```

Use as the type for `zdc.port()` (initiator) or `zdc.export()` (target)
fields on a component. The `__bind__` map connects export methods to
implementation coroutines.

See `docs/interface_protocols.rst` and `docs/split_transactions.rst`.

---

## Simulation Entry Points

### `zdc.simulate`

Constructs a root component and runs the simulation to completion (or until
`shutdown()` is called).

```python
zdc.simulate(TopComponent)
```

### `zdc.SimDomain`

Manages a shared simulation time context across a component tree. Required
when composing multiple independently-timed subsystems.

---

## Concurrent Execution

### `@zdc.process`

Marks an `async` method as an independent background coroutine. Starts
lazily when the first `wait()` call is made anywhere in the component tree.

Use for: monitors, clock generators, protocol checkers.  
Avoid for: operations-level BFMs — use plain `async` methods instead.

```python
@zdc.process
async def monitor(self):
    while True:
        status = await self.regs.status.read()
        if status.error:
            print("Error detected!")
        await self.wait(zdc.Time.ns(100))
```

### `zdc.spawn` / `zdc.SpawnHandle`

Spawn concurrent coroutines within a component's simulation context.
`SpawnHandle` lets the caller join or cancel the spawned task.

### `zdc.gather`

Collects results from multiple concurrent awaitables — like `asyncio.gather`
but integrated with Zuspec simulation time.

---

## Signaling and Synchronization

### `zdc.posedge` / `zdc.negedge` / `zdc.edge`

Awaitable edge detectors for synchronizing on clock or signal transitions.

### `zdc.Event`

Interrupt-style signaling backed by `asyncio.Event`. Components can
`await` an event or bind a callback via the `at` field.

---

## Data Transport

### `zdc.Queue` / `zdc.queue`

Typed FIFO queues for passing data between concurrent behaviors.
Use `async get` / `async put` patterns.

### TLM Channels

Transaction-Level Modeling primitives for abstract bus and interface
modeling:

| Class | Role |
|---|---|
| `zdc.Channel` | Generic TLM channel |
| `zdc.PutIF` / `zdc.GetIF` | Unidirectional push/pull interfaces |
| `zdc.ReqRspChannel` / `zdc.ReqRspIF` | Request/response channel |
| `zdc.Transport` | Blocking transport interface |

---

## PSS Flow Objects

Base classes for PSS-style resource and data-flow modeling:

| Class | Semantics |
|---|---|
| `zdc.Buffer` | Consumed once (point-to-point data) |
| `zdc.Stream` | Streamed data (FIFO semantics) |
| `zdc.State` | Shared mutable state |
| `zdc.Resource` | Locked/released hardware resource |
