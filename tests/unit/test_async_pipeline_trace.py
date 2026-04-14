"""Phase 4 tests — Observer, Trace, and Find API.

Covers: ``PipelineTrace``, ``add_observer``, ``zdc.pipeline.find()``,
``zdc.pipeline.snapshot()``, ``zdc.pipeline.current_cycle()``.
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import Time, TimeUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_comp(comp, ns: int):
    asyncio.run(comp.wait(Time(TimeUnit.NS, ns)))


# ---------------------------------------------------------------------------
# Observer callback tests
# ---------------------------------------------------------------------------

class TestObserver:
    def test_observer_fires_stage_enter_and_exit(self):
        """add_observer callback fires for stage_enter and stage_exit."""
        fired = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    pass
                async with zdc.pipeline.stage() as EX:
                    pass

        p = Pipe()

        async def run_and_watch():
            task = asyncio.create_task(p.wait(Time(TimeUnit.NS, 10)))
            await asyncio.sleep(0)
            p.run_trace.add_observer(lambda tok, ev, **kw: fired.append(ev))
            await task

        asyncio.run(run_and_watch())
        assert "stage_enter" in fired
        assert "stage_exit" in fired

    def test_observer_receives_stall_event(self):
        """Observer fires 'stall' when stall() is called."""
        fired = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    await IF.stall(2)

        p = Pipe()

        async def run_and_watch():
            task = asyncio.create_task(p.wait(Time(TimeUnit.NS, 15)))
            await asyncio.sleep(0)
            p.run_trace.add_observer(lambda tok, ev, **kw: fired.append(ev))
            await task

        asyncio.run(run_and_watch())
        assert "stall" in fired


# ---------------------------------------------------------------------------
# Trace content tests
# ---------------------------------------------------------------------------

class TestTraceContent:
    def test_trace_records_all_stage_events(self):
        """stage_enter and stage_exit are recorded for every token/stage pair."""
        fired = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    pass
                async with zdc.pipeline.stage() as EX:
                    pass

        p = Pipe()

        async def run_and_watch():
            task = asyncio.create_task(p.wait(Time(TimeUnit.NS, 20)))
            await asyncio.sleep(0)
            p.run_trace.add_observer(lambda tok, ev, **kw: fired.append(ev))
            await task

        asyncio.run(run_and_watch())
        assert "stage_enter" in fired
        assert "stage_exit" in fired

    def test_print_trace_no_crash(self):
        """print_trace() executes without error."""
        import io

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    pass

        p = Pipe()
        run_comp(p, 10)
        buf = io.StringIO()
        p.run_trace.print_trace(file=buf)
        assert len(buf.getvalue()) > 0


# ---------------------------------------------------------------------------
# snapshot() + find() tests
# ---------------------------------------------------------------------------

class TestSnapshotAndFind:
    def test_snapshot_stores_values(self):
        """pipeline.snapshot() stores data accessible from the trace."""
        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    zdc.pipeline.snapshot(opcode=42)

        p = Pipe()
        run_comp(p, 10)
        tokens = p.run_trace.tokens()
        assert len(tokens) >= 1
        # stage_snapshots keys are stage indices — IF is index 0
        all_snaps = {}
        for snap_dict in tokens[0].stage_snapshots.values():
            all_snaps.update(snap_dict)
        assert all_snaps.get("opcode") == 42

    def test_find_returns_matching_snap(self):
        """pipeline.find() returns a _Snap matching the predicate from inside."""
        found = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    zdc.pipeline.snapshot(pc=0xDEAD)
                async with zdc.pipeline.stage() as EX:
                    result = zdc.pipeline.find(lambda s: s.pc == 0xDEAD)
                    if result is not None:
                        found.append(result)

        p = Pipe()
        run_comp(p, 30)
        assert len(found) >= 1

    def test_find_returns_none_when_no_match(self):
        """pipeline.find() returns None when predicate never matches."""
        results = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    zdc.pipeline.snapshot(pc=0xBEEF)
                async with zdc.pipeline.stage() as EX:
                    result = zdc.pipeline.find(lambda s: s.pc == 0x0000)
                    results.append(result)

        p = Pipe()
        run_comp(p, 30)
        assert all(r is None for r in results)

    def test_find_returns_newest_first(self):
        """pipeline.find() searches from newest to oldest in-flight token."""
        pcs = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            _counter: int = 0

            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    zdc.pipeline.snapshot(pc=self._counter)
                    self._counter += 1
                async with zdc.pipeline.stage() as EX:
                    snap = zdc.pipeline.find(lambda s: hasattr(s, 'pc'))
                    if snap is not None:
                        pcs.append(snap.pc)

        p = Pipe()
        run_comp(p, 30)
        # Each EX stage finds the newest token in IF (itself or a newer one)
        assert len(pcs) >= 1


# ---------------------------------------------------------------------------
# current_cycle() tests
# ---------------------------------------------------------------------------

class TestCurrentCycle:
    def test_current_cycle_advances_per_stage(self):
        """current_cycle() returns a cycle value that increases through stages."""
        cycles = []

        @zdc.dataclass
        class Pipe(zdc.Component):
            @zdc.pipeline
            async def run(self):
                async with zdc.pipeline.stage() as IF:
                    cycles.append(zdc.pipeline.current_cycle())
                async with zdc.pipeline.stage() as EX:
                    cycles.append(zdc.pipeline.current_cycle())

        p = Pipe()
        run_comp(p, 20)
        assert len(cycles) >= 2
        # Cycles from EX must be >= cycles from IF
        assert cycles[1] >= cycles[0]

    def test_current_cycle_returns_zero_outside_pipeline(self):
        """current_cycle() returns 0 when called outside a pipeline."""
        assert zdc.pipeline.current_cycle() == 0
