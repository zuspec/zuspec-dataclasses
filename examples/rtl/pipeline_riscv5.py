#!/usr/bin/env python3
"""5-stage pipelined processor behavioral model with RAW hazard tracking.

Demonstrates the full ``@zdc.pipeline`` hazard API with the new explicit
port and clock-domain API:

  IF   — instruction fetch via ``InPort``; reserve destination register
  ID   — instruction decode; block on source registers (RAW hazard wait)
  EX   — execute ALU op; write result to bypass network
  MEM  — memory stage (pass-through for ALU ops in this model)
  WB   — write-back; release register file entry; emit result via ``OutPort``

New API highlights:
  * ``clk: zdc.ClockDomain = zdc.clock_domain()``  — first-class clock domain
  * ``insn_in: zdc.InPort[tuple] = zdc.in_port()`` — ingress instruction port
  * ``wb_out: zdc.OutPort[tuple] = zdc.out_port()`` — egress write-back port
  * ``@zdc.pipeline(clock_domain=lambda s: s.clk)`` — explicit clock binding

Hazard protocol (``PipelineResource`` with ``BypassLock``):
  * ``zdc.pipeline.reserve(rf[rd])``  — claim write slot in IF
  * ``zdc.pipeline.block(rf[rs])``    — stall until rs is ready (in ID)
  * ``zdc.pipeline.write(rf[rd], v)`` — forward result in EX
  * ``zdc.pipeline.release(rf[rd])``  — free the slot in WB

Run (behavioral simulation)::

    python3 pipeline_riscv5.py

Run (RTL synthesis to Verilog)::

    python3 -c "
    from pipeline_riscv5 import RiscV5
    from zuspec.synth import synthesize_pipeline
    print(synthesize_pipeline(RiscV5))
    "

The synthesizer detects the ``PipelineResource(lock=BypassLock())`` field,
generates an inlined RTL register-file array, and emits bypass forwarding
muxes for the WB→ID RAW hazard.  See ``docs/async_pipeline_synthesis.rst``
for the developer guide.

Expected output: a Gantt trace; tokens that depend on a not-yet-written
register will show stall cycles in the ID stage.
"""

import asyncio
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit


# ---------------------------------------------------------------------------
# Toy instruction set
# ---------------------------------------------------------------------------

ADD   = "ADD"
ADDI  = "ADDI"
NOP   = "NOP"

# Simple register-register ADD instructions
PROGRAM = [
    (ADD,  1, 2, 3),   # r1 = r2 + r3
    (ADD,  4, 1, 3),   # r4 = r1 + r3  ← RAW hazard on r1
    (NOP,  0, 0, 0),
    (ADD,  5, 4, 2),   # r5 = r4 + r2  ← RAW hazard on r4
    (NOP,  0, 0, 0),
    (NOP,  0, 0, 0),
]


# ---------------------------------------------------------------------------
# Pipeline component
# ---------------------------------------------------------------------------

@zdc.dataclass
class RiscV5(zdc.Component):
    """5-stage pipelined processor behavioral model."""

    # First-class clock domain (supplies wait_cycle() to pipeline stages)
    clk: zdc.ClockDomain = zdc.clock_domain()

    # Instruction ingress port: (op, rd, rs1, rs2) tuples arrive here each cycle
    insn_in: zdc.InPort[tuple] = zdc.in_port()

    # Write-back egress port: (rd, result) for non-NOP instructions
    wb_out: zdc.OutPort[tuple] = zdc.out_port()

    # Register file with bypass-lock hazard tracking (32 entries)
    rf: object = zdc.field(
        default_factory=lambda: zdc.pipeline.resource(32, lock=zdc.BypassLock())
    )

    # Register file state — initialize r2=10, r3=5 so ADD results are visible
    _regs: object = zdc.field(default_factory=lambda: [0, 0, 10, 5] + [0] * 28)

    @zdc.pipeline(clock_domain=lambda s: s.clk)
    async def _execute(self):
        # --- IF: Instruction Fetch — receive instruction from InPort ---
        async with zdc.pipeline.stage() as IF:
            op, rd, rs1, rs2 = await self.insn_in.get()
            zdc.pipeline.snapshot(op=op, rd=rd, rs1=rs1, rs2=rs2)
            # Reserve destination register (write slot)
            if op != NOP and rd != 0:
                await zdc.pipeline.reserve(self.rf[rd])

        # --- ID: Instruction Decode / Register Read ---
        async with zdc.pipeline.stage() as ID:
            # block() returns the bypassed value when a prior token reserved+wrote
            # the register, or None when no write is in-flight (read from reg file).
            if op != NOP:
                bypassed1 = await zdc.pipeline.block(self.rf[rs1]) if rs1 != 0 else None
                val1 = bypassed1 if bypassed1 is not None else self._regs[rs1]
                bypassed2 = await zdc.pipeline.block(self.rf[rs2]) if rs2 != 0 else None
                val2 = bypassed2 if bypassed2 is not None else self._regs[rs2]
            else:
                val1 = val2 = 0

        # --- EX: Execute ---
        async with zdc.pipeline.stage() as EX:
            if op == ADD:
                result = val1 + val2
            elif op == ADDI:
                result = val1 + rs2   # rs2 field holds immediate in ADDI
            else:
                result = 0
            # Forward result through bypass network
            if op != NOP and rd != 0:
                zdc.pipeline.write(self.rf[rd], result)

        # --- MEM: Memory Access (pass-through for ALU ops) ---
        async with zdc.pipeline.stage() as MEM:
            pass  # memory ops not modelled in this example

        # --- WB: Write-Back — update register file; emit result via OutPort ---
        async with zdc.pipeline.stage() as WB:
            if op != NOP and rd != 0:
                self._regs[rd] = result
                zdc.pipeline.release(self.rf[rd])
                await self.wb_out.put((rd, result))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("5-Stage RISC-V-like Pipeline (RAW hazard demo)")
    print("=" * 55)
    print()
    print("Program:")
    for i, insn in enumerate(PROGRAM):
        op, rd, rs1, rs2 = insn
        if op == NOP:
            print(f"  [{i}] NOP")
        else:
            print(f"  [{i}] {op}  r{rd}, r{rs1}, r{rs2}")
    print()

    cpu = RiscV5()
    wb_results = []

    async def run():
        # Feed instructions through InPort and drain write-back results
        async def feed():
            for insn in PROGRAM:
                await cpu.insn_in._put(insn)
            # Flush: send extra NOPs so all in-flight tokens reach WB
            for _ in range(5):
                await cpu.insn_in._put((NOP, 0, 0, 0))

        async def drain():
            for _ in PROGRAM:
                item = await cpu.wb_out._get()
                if item is not None:
                    wb_results.append(item)

        task = asyncio.create_task(cpu.wait(Time(TimeUnit.NS, 40)))
        await asyncio.gather(feed(), drain())
        await task

    asyncio.run(run())

    print("Register file after simulation:")
    for i, v in enumerate(cpu._regs):
        if v != 0:
            print(f"  r{i} = {v}")
    print()
    print("Pipeline trace (cycles):")
    cpu._execute_trace.print_trace()
