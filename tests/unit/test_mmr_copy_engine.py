"""End-to-end integration test: memory copy engine.

Simulates a software driver and a hardware copy engine communicating through
an abstract register file.  No @zdc.dataclass / @zdc.proc is needed; we model
everything with plain asyncio coroutines.
"""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.mmr.base import RegisterFile
from zuspec.dataclasses.mmr.wait import wait_until


# ---------------------------------------------------------------------------
# Register file declaration
# ---------------------------------------------------------------------------

@zdc.regfile
class DMARegs(RegisterFile):

    @zdc.reg(offset=0x00)
    class CTRL:
        START: zdc.u1 = zdc.FieldAttr.Pulse      # singlepulse: SW writes 1; self-clears
        ABORT: zdc.u1 = zdc.FieldAttr.Pulse

    @zdc.reg(offset=0x04)
    class STATUS:
        BUSY:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W,
                                       hwset=True, hwclr=True, default=0)
        DONE:  zdc.u1 = zdc.FieldAttr.StickyBit
        ERROR: zdc.u1 = zdc.FieldAttr.StickyBit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _make_regs():
    return DMARegs()


async def _sw_start(regs):
    """Software driver: start a transfer, wait for DONE or ERROR."""
    regs.CTRL._fields['START'].write(1)   # singlepulse start
    # Wait for DONE or ERROR
    await wait_until(regs.STATUS,
                     lambda s: s.DONE == 1 or s.ERROR == 1)
    done  = regs.STATUS._fields['DONE'].value
    error = regs.STATUS._fields['ERROR'].value
    # SW clear both sticky bits
    regs.STATUS._fields['DONE'].write(1)   # woclr
    regs.STATUS._fields['ERROR'].write(1)  # woclr
    return done == 1 and error == 0


async def _hw_copy_success(regs):
    """Hardware engine: wait for START, assert BUSY, complete."""
    await regs.CTRL._fields['START'].wait_set()
    regs.STATUS._fields['BUSY']._hw_assign(1)
    await asyncio.sleep(0)   # simulate work
    regs.STATUS._fields['DONE']._hw_assign(1)
    regs.STATUS._fields['BUSY']._hw_assign(0)


async def _hw_copy_error(regs):
    """Hardware engine: wait for START, assert BUSY, then report error."""
    await regs.CTRL._fields['START'].wait_set()
    regs.STATUS._fields['BUSY']._hw_assign(1)
    await asyncio.sleep(0)
    regs.STATUS._fields['ERROR']._hw_assign(1)
    regs.STATUS._fields['BUSY']._hw_assign(0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_successful_copy():
    async def _test():
        regs = _make_regs()
        asyncio.ensure_future(_hw_copy_success(regs))
        result = await _sw_start(regs)
        assert result is True

    _run(_test())


def test_error_path():
    async def _test():
        regs = _make_regs()
        asyncio.ensure_future(_hw_copy_error(regs))
        result = await _sw_start(regs)
        assert result is False

    _run(_test())


def test_busy_cleared_after_copy():
    async def _test():
        regs = _make_regs()
        asyncio.ensure_future(_hw_copy_success(regs))
        await _sw_start(regs)
        assert regs.STATUS._fields['BUSY'].value == 0

    _run(_test())


def test_start_self_clears():
    async def _test():
        regs = _make_regs()
        regs.CTRL._fields['START'].write(1)
        assert regs.CTRL._fields['START'].value == 1
        await asyncio.sleep(0)   # singlepulse_clear starts
        await asyncio.sleep(0)   # singlepulse_clear completes
        assert regs.CTRL._fields['START'].value == 0

    _run(_test())


def test_done_and_error_cleared_after_sw_read():
    async def _test():
        regs = _make_regs()
        asyncio.ensure_future(_hw_copy_success(regs))
        await _sw_start(regs)
        # After _sw_start clears DONE, check it is 0
        assert regs.STATUS._fields['DONE'].value == 0

    _run(_test())


def test_irq_handler_wakes():
    """A separate IRQ handler coroutine wakes on DONE or ERROR."""
    async def _test():
        regs = _make_regs()
        irq_log = []

        async def _irq_handler():
            while True:
                await wait_until(regs.STATUS,
                                 lambda s: s.DONE == 1 or s.ERROR == 1)
                irq_log.append(('irq', regs.STATUS._fields['DONE'].value,
                                 regs.STATUS._fields['ERROR'].value))
                # Clear bits and break for test simplicity
                regs.STATUS._fields['DONE'].write(1)
                regs.STATUS._fields['ERROR'].write(1)
                break

        asyncio.ensure_future(_irq_handler())
        asyncio.ensure_future(_hw_copy_success(regs))
        # Kick off the copy
        regs.CTRL._fields['START'].write(1)
        # Let everything settle
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(irq_log) == 1
        assert irq_log[0] == ('irq', 1, 0)

    _run(_test())


# ---------------------------------------------------------------------------
# Tests from plan §7.10
# ---------------------------------------------------------------------------

class CopyEngineDriver:
    """Minimal software driver modelling a CopyEngineDriver.run() interface."""

    def __init__(self, regs: DMARegs):
        self._regs = regs

    async def run(self) -> bool:
        """Start a transfer and wait for completion. Returns True on success."""
        regs = self._regs
        regs.CTRL._fields['START'].write(1)
        await wait_until(regs.STATUS,
                         lambda s: s.DONE == 1 or s.ERROR == 1)
        done  = regs.STATUS._fields['DONE'].value
        error = regs.STATUS._fields['ERROR'].value
        regs.STATUS._fields['DONE'].write(1)
        regs.STATUS._fields['ERROR'].write(1)
        return done == 1 and error == 0


def test_driver_run_returns_true():
    """CopyEngineDriver.run() returns True on successful copy."""
    async def _test():
        regs = _make_regs()
        driver = CopyEngineDriver(regs)
        asyncio.ensure_future(_hw_copy_success(regs))
        result = await driver.run()
        assert result is True

    _run(_test())


def test_driver_run_returns_false():
    """CopyEngineDriver.run() returns False when hardware reports error."""
    async def _test():
        regs = _make_regs()
        driver = CopyEngineDriver(regs)
        asyncio.ensure_future(_hw_copy_error(regs))
        result = await driver.run()
        assert result is False

    _run(_test())


def test_stickybit_no_loss_under_load():
    """Two sequential HW completion pulses: both DONE stickybit events captured.

    With stickybit=posedge, a rising edge (0→1) on the HW input sets the bit.
    The HW de-asserts between pulses (1→0→1) so each rising edge is a distinct
    event.  The no-loss guarantee means the bit stays set if SW hasn't cleared
    it yet when the second pulse arrives.
    """
    async def _test():
        regs = _make_regs()
        done_count = 0

        async def _hw_two_pulses():
            regs.STATUS._fields['DONE']._hw_assign(1)  # first pulse (rising edge)
            regs.STATUS._fields['DONE']._hw_assign(0)  # de-assert
            await asyncio.sleep(0)                     # yield; SW clears DONE
            regs.STATUS._fields['DONE']._hw_assign(1)  # second pulse (rising edge)
            regs.STATUS._fields['DONE']._hw_assign(0)  # de-assert

        async def _sw_reader():
            nonlocal done_count
            while done_count < 2:
                await wait_until(regs.STATUS, lambda s: s.DONE == 1)
                done_count += 1
                regs.STATUS._fields['DONE'].write(1)  # woclr clear
                await asyncio.sleep(0)

        asyncio.ensure_future(_hw_two_pulses())
        await _sw_reader()
        assert done_count == 2

    _run(_test())


def test_concurrent_waiters():
    """Two coroutines both waiting on STATUS; both notified when DONE fires."""
    async def _test():
        regs = _make_regs()
        results = []

        async def _waiter(tag):
            await wait_until(regs.STATUS, lambda s: s.DONE == 1)
            results.append(tag)

        asyncio.ensure_future(_waiter('a'))
        asyncio.ensure_future(_waiter('b'))
        await asyncio.sleep(0)   # let both park

        regs.STATUS._fields['DONE']._hw_assign(1)  # wake both
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert sorted(results) == ['a', 'b']

    _run(_test())


def test_swmod_callback_fires():
    """Callback registered via on_write on CTRL fires when SW bus-writes START."""
    async def _test():
        regs = _make_regs()
        log = []

        regs.CTRL.on_write(lambda old, new: log.append((old, new)))

        regs.CTRL.bus_write(1)   # SW bus write; fires on_write callbacks
        assert len(log) == 1
        assert log[0][1] & 0x1 == 1   # START bit set in new word

    _run(_test())
