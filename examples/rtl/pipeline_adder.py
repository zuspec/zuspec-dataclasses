#!/usr/bin/env python3
"""3-stage integer adder pipeline behavioral model.

Demonstrates the new ``@zdc.pipeline`` API with explicit ingress/egress ports:

  FETCH   — read operands via ``in_data.get()``
  COMPUTE — add them together
  WRITEBACK — post result via ``out_data.put()``

Run (behavioral simulation)::

    python3 pipeline_adder.py

Run (RTL synthesis to Verilog)::

    python3 -c "
    from pipeline_adder import Adder
    from zuspec.synth import synthesize_pipeline
    print(synthesize_pipeline(Adder))
    "
"""

import asyncio
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit


@zdc.dataclass
class Adder(zdc.Component):
    """3-stage pipelined integer adder with explicit InPort/OutPort."""

    clk: zdc.ClockDomain = zdc.clock_domain()

    a_in:    zdc.InPort[zdc.u32]  = zdc.in_port()
    b_in:    zdc.InPort[zdc.u32]  = zdc.in_port()
    sum_out: zdc.OutPort[zdc.u32] = zdc.out_port()

    @zdc.pipeline(clock_domain=lambda s: s.clk)
    async def _pipeline(self):
        a, b = await self.a_in.get(), await self.b_in.get()

        async with zdc.pipeline.stage() as FETCH:
            pass  # operands already captured

        async with zdc.pipeline.stage() as COMPUTE:
            result = a + b

        async with zdc.pipeline.stage() as WRITEBACK:
            await self.sum_out.put(result)


if __name__ == "__main__":
    print("3-Stage Adder Pipeline (InPort/OutPort API)")
    print("=" * 50)

    adder = Adder()

    async def driver():
        for i in range(10):
            await adder.a_in.drive(i)
            await adder.b_in.drive(i * 2)

    async def collector():
        for _ in range(10):
            val = await adder.sum_out.collect()
            print(f"  sum_out = {val}")

    async def run():
        await asyncio.gather(
            adder.wait(Time(TimeUnit.NS, 50)),
            driver(),
            collector(),
        )

    asyncio.run(run())
