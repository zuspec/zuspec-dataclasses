---
name: zuspec-dataclasses
description: >
  Modeling digital hardware in Python with zuspec.dataclasses (zdc).
  Use this skill when writing, reading, or analyzing Zuspec models:
  RTL components (@zdc.sync/@zdc.comb), MLS pipeline descriptions
  (@zdc.pipeline), transaction-level synthesizable processes (@zdc.proc),
  behavioral/BFM models, action-based test scenarios,
  constraints, coverage, and register/memory maps.
license: Apache-2.0
---

# Zuspec Modeling with Python (`zuspec.dataclasses`)

`import zuspec.dataclasses as zdc` — Python-embedded language for
multi-abstraction hardware modeling (behavioral → MLS → RTL).

> **Important:** Zuspec tools require access to the *source file* of every
> class they process. Always write classes to a real file; never pass them
> as strings.

## Abstraction levels

| Level | Key constructs | Reference |
|---|---|---|
| **Core** (all levels) | `zdc.Component`, `@zdc.dataclass`, ports, fields, binding, scalar types | [references/core.md](references/core.md) |
| **Design** – RTL & MLS | `@zdc.sync`, `@zdc.comb`, `zdc.RegFile`, `zdc.Memory`, `@zdc.pipeline`, `@zdc.proc` | [references/design.md](references/design.md) |
| **Behavioral** – BFMs & simulation | `zdc.IfProtocol`, `zdc.Queue`, `zdc.spawn`, `zdc.simulate`, TLM channels | [references/behavioral.md](references/behavioral.md) |
| **Verification** – tests & coverage | `zdc.rand`, `@zdc.constraint`, `zdc.Covergroup`, `zdc.Action`, `zdc.ScenarioRunner` | [references/verification.md](references/verification.md) |

Load only the reference file(s) relevant to your task.
