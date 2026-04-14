"""Tests for zdc.simulate() — async context manager API."""
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _posedge(counter):
    """Toggle clock high→low, advancing simulation by one cycle."""
    counter.clock = 1
    await counter.wait(zdc.Time.ns(5))
    counter.clock = 0
    await counter.wait(zdc.Time.ns(5))


async def _cycles(counter, n: int):
    for _ in range(n):
        await _posedge(counter)


# ---------------------------------------------------------------------------
# Test component
# ---------------------------------------------------------------------------

@zdc.dataclass
class EnableCounter(zdc.Component):
    """Simple enable-gated counter for simulate() tests."""
    clock  : zdc.bit   = zdc.input()
    reset  : zdc.bit   = zdc.input()
    enable : zdc.bit   = zdc.input()
    count  : zdc.bit32 = zdc.output()

    @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
    def _count(self):
        if self.reset:
            self.count = 0
        elif self.enable:
            self.count = self.count + 1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulate_basic_counter():
    """simulate() creates a counter; 10 enabled cycles → count == 10."""
    async with zdc.simulate(EnableCounter) as counter:
        # Apply reset
        counter.reset = 1
        await _cycles(counter, 2)
        assert counter.count == 0

        # Release reset, enable counting
        counter.reset = 0
        counter.enable = 1
        await _cycles(counter, 10)
        assert counter.count == 10


@pytest.mark.asyncio
async def test_simulate_reset_holds():
    """Counter stays at zero while reset is asserted."""
    async with zdc.simulate(EnableCounter) as counter:
        counter.enable = 1
        counter.reset = 1
        await _cycles(counter, 5)
        assert counter.count == 0

        counter.reset = 0
        await _cycles(counter, 5)
        assert counter.count == 5


@pytest.mark.asyncio
async def test_simulate_count_increments_only_when_enabled():
    """count only increments when enable is high."""
    async with zdc.simulate(EnableCounter) as counter:
        counter.reset = 1
        await _cycles(counter, 1)
        counter.reset = 0

        counter.enable = 0
        await _cycles(counter, 5)
        assert counter.count == 0

        counter.enable = 1
        await _cycles(counter, 3)
        assert counter.count == 3


@pytest.mark.asyncio
async def test_simulate_returns_component_instance():
    """The context variable is the actual EnableCounter instance."""
    async with zdc.simulate(EnableCounter) as counter:
        assert isinstance(counter, EnableCounter)


@pytest.mark.asyncio
async def test_simulate_close_called_on_exit(tmp_path):
    """close() is called on __aexit__; VCD file is created and non-empty."""
    vcd_path = str(tmp_path / "trace.vcd")
    async with zdc.simulate(EnableCounter, vcd=vcd_path) as counter:
        counter.reset = 1
        await _cycles(counter, 2)
        counter.reset = 0
        counter.enable = 1
        await _cycles(counter, 5)

    import os
    assert os.path.exists(vcd_path), "VCD file should be written on close"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
