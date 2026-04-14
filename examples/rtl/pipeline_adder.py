#!/usr/bin/env python3
"""3-stage integer adder pipeline behavioral model.

Demonstrates the basic ``@zdc.pipeline`` API with no hazards:

  FETCH   — read operands from input ports
  COMPUTE — add them together
  WRITEBACK — post result to output port

Run::

    python3 pipeline_adder.py

Expected output: a Gantt-style pipeline trace showing each token's stage
enter/exit cycles and the computed results.
"""

import asyncio
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit


@zdc.dataclass
class Adder(zdc.Component):
    """3-stage pipelined integer adder."""

    clock: zdc.bit = zdc.input()
    reset: zdc.bit = zdc.input()

    a_in:    zdc.u32 = zdc.input()
    b_in:    zdc.u32 = zdc.input()
    sum_out: zdc.u32 = zdc.output()

    @zdc.pipeline(clock=lambda s: s.clock, reset=lambda s: s.reset)
    async def _pipeline(self):
        async with zdc.pipeline.stage() as FETCH:
            a = self.a_in
            b = self.b_in

        async with zdc.pipeline.stage() as COMPUTE:
            result = a + b

        async with zdc.pipeline.stage() as WRITEBACK:
            self.sum_out = result


if __name__ == "__main__":
    print("3-Stage Adder Pipeline")
    print("=" * 50)

    p = Adder()

    def on_event(tok, ev, **kw):
        if ev == "stage_enter":
            stage = kw.get("stage", "?")
            print(f"  tok={tok.token_id}  stage={stage}  enter_cycle={tok.enter_cycles.get(stage, '?')}")

    async def run():
        task = asyncio.create_task(p.wait(Time(TimeUnit.NS, 30)))
        await asyncio.sleep(0)
        p._pipeline_trace.add_observer(on_event)
        await task

    asyncio.run(run())
    print()
    print("Pipeline trace:")
    p._pipeline_trace.print_trace()
