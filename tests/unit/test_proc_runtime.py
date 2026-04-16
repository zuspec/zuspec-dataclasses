"""Runtime smoke test for @proc + Reg[T] fields."""
import asyncio
import pytest
import zuspec.dataclasses as zdc


@zdc.dataclass
class Counter(zdc.Component):
    count: zdc.Reg[zdc.b32] = zdc.output()

    @zdc.proc
    async def _count(self):
        while True:
            await self.count.write(self.count.read() + 1)


def test_count_field_is_regprocrt():
    """count field must be a RegProcRT, not a plain int."""
    from zuspec.dataclasses.rt.regfile_rt import RegProcRT
    c = Counter()
    assert isinstance(c.count, RegProcRT), f"Expected RegProcRT, got {type(c.count)}"


def test_read_is_sync():
    """read() must be synchronous and return the current value."""
    from zuspec.dataclasses.rt.regfile_rt import RegProcRT
    c = Counter()
    assert isinstance(c.count, RegProcRT)
    val = c.count.read()
    assert val == 0


def test_counter_runs_5_cycles():
    """Running 5 cycles should increment count to 5."""
    async def run():
        c = Counter()
        task = asyncio.create_task(c._impl._proc_processes[0][1].method(c))
        await c._impl.wait_cycles(5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return c.count.read()

    result = asyncio.run(run())
    assert result == 5, f"Expected count==5, got {result}"
