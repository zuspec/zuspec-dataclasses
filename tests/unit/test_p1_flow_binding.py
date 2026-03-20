"""P1 tests: flow-object binding lifecycle and randomization.

Verifies that:
1. Buffer flow objects are randomized (rand fields get non-default values).
2. Producer sees the flow object *before* pre_solve() / randomize() / body().
3. Consumer sees the same concrete flow object before pre_solve() / body().
4. Both producer and consumer reference the identical flow object instance.
5. FlowObjectConstraintStore scaffolding works correctly.
"""
from __future__ import annotations

import asyncio

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.activity_dsl import do
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner
from zuspec.dataclasses.rt.flow_constraint_store import FlowObjectConstraintStore


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Domain model  (all action/buffer types must be at module scope for parser)
# ---------------------------------------------------------------------------

@zdc.dataclass
class MyComp(zdc.Component):
    pass


@zdc.dataclass
class DataBuf(zdc.Buffer):
    """Buffer with rand fields so randomize() can solve them."""
    addr: zdc.u32 = zdc.rand()
    size: zdc.u16 = zdc.rand()


@zdc.dataclass
class BufNoRand(zdc.Buffer):
    """Buffer with no rand fields — randomize() should not crash."""
    tag: int = 0


# ---------------------------------------------------------------------------
# Module-level action types used by runtime tests
# ---------------------------------------------------------------------------

# -- Probe: captures addr/size from the flow object in body() --

_probe_results: list = []   # shared mutable list; tests reset before use


@zdc.dataclass
class _ProbeProducer(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_output()
    async def body(self) -> None:
        _probe_results.append(("addr", self.buf.addr))
        _probe_results.append(("size", self.buf.size))


@zdc.dataclass
class _ProbeConsumer(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_input()
    async def body(self) -> None:
        pass


@zdc.dataclass
class _ProbeTransfer(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_ProbeProducer)
            await do(_ProbeConsumer)


# -- NoRand: buffer has no rand fields --

@zdc.dataclass
class _NRProd(zdc.Action[MyComp]):
    buf: BufNoRand = zdc.flow_output()
    async def body(self) -> None: pass


@zdc.dataclass
class _NRCons(zdc.Action[MyComp]):
    buf: BufNoRand = zdc.flow_input()
    async def body(self) -> None: pass


@zdc.dataclass
class _NRTransfer(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_NRProd)
            await do(_NRCons)


# -- ConsBody: consumer records body() flow object --

_cons_body_values: list = []


@zdc.dataclass
class _ProdCB(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_output()
    async def body(self) -> None: pass


@zdc.dataclass
class _ConsCB(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_input()
    async def body(self) -> None:
        _cons_body_values.append(self.buf)


@zdc.dataclass
class _XferCB(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_ProdCB)
            await do(_ConsCB)


# -- PreSolveProd: producer records flow object at pre_solve --

_prod_pre_values: list = []
_prod_body_values: list = []


@zdc.dataclass
class _ProdPS(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_output()
    def pre_solve(self) -> None:
        _prod_pre_values.append(self.buf)
    async def body(self) -> None:
        _prod_body_values.append(self.buf)


@zdc.dataclass
class _ConsPS(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_input()
    async def body(self) -> None: pass


@zdc.dataclass
class _XferPS(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_ProdPS)
            await do(_ConsPS)


# -- SameInst: producer and consumer capture their buf reference --

_prod_bufs: list = []
_cons_bufs: list = []


@zdc.dataclass
class _ProdSI(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_output()
    async def body(self) -> None:
        _prod_bufs.append(self.buf)


@zdc.dataclass
class _ConsSI(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_input()
    async def body(self) -> None:
        _cons_bufs.append(self.buf)


@zdc.dataclass
class _XferSI(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_ProdSI)
            await do(_ConsSI)


# -- ConsPreSolve: consumer records flow object at pre_solve --

_cons_pre_values: list = []


@zdc.dataclass
class _ProdCP(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_output()
    async def body(self) -> None: pass


@zdc.dataclass
class _ConsCP(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_input()
    def pre_solve(self) -> None:
        _cons_pre_values.append(self.buf)
    async def body(self) -> None: pass


@zdc.dataclass
class _XferCP(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_ProdCP)
            await do(_ConsCP)


# -- Consistent values: both producer and consumer record addr/size --

_prod_state: dict = {}
_cons_state: dict = {}


@zdc.dataclass
class _ProdCV(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_output()
    async def body(self) -> None:
        _prod_state['addr'] = self.buf.addr
        _prod_state['size'] = self.buf.size


@zdc.dataclass
class _ConsCV(zdc.Action[MyComp]):
    buf: DataBuf = zdc.flow_input()
    async def body(self) -> None:
        _cons_state['addr'] = self.buf.addr
        _cons_state['size'] = self.buf.size


@zdc.dataclass
class _XferCV(zdc.Action[MyComp]):
    async def activity(self) -> None:
        with zdc.schedule():
            await do(_ProdCV)
            await do(_ConsCV)


# ---------------------------------------------------------------------------
# Tests: FlowObjectConstraintStore scaffolding
# ---------------------------------------------------------------------------

class TestFlowObjectConstraintStore:
    def test_empty_store_returns_empty_list(self):
        store = FlowObjectConstraintStore()
        key = (_ProdCB, _ConsCB, "buf")
        assert store.consumer_constraints_for(key) == []

    def test_register_and_retrieve(self):
        store = FlowObjectConstraintStore()
        key = (_ProdCB, _ConsCB, "buf")
        fn = lambda: None
        store.register_consumer(key, [fn])
        assert store.consumer_constraints_for(key) == [fn]

    def test_multiple_registrations_accumulate(self):
        store = FlowObjectConstraintStore()
        key = (_ProdCB, _ConsCB, "buf")
        fn1, fn2 = lambda: None, lambda: None
        store.register_consumer(key, [fn1])
        store.register_consumer(key, [fn2])
        result = store.consumer_constraints_for(key)
        assert fn1 in result and fn2 in result and len(result) == 2

    def test_clear_specific_key(self):
        store = FlowObjectConstraintStore()
        key = (_ProdCB, _ConsCB, "buf")
        store.register_consumer(key, [lambda: None])
        store.clear(key)
        assert store.consumer_constraints_for(key) == []
        assert len(store) == 0

    def test_clear_all(self):
        store = FlowObjectConstraintStore()
        k1 = (_ProdCB, _ConsCB, "buf")
        k2 = (_ConsCB, _ProdCB, "buf")
        store.register_consumer(k1, [lambda: None])
        store.register_consumer(k2, [lambda: None])
        store.clear()
        assert len(store) == 0

    def test_len_counts_callables(self):
        store = FlowObjectConstraintStore()
        key = (_ProdCB, _ConsCB, "buf")
        store.register_consumer(key, [lambda: None, lambda: None])
        assert len(store) == 2

    def test_retrieve_returns_copy(self):
        """Modifying the returned list must not affect the store."""
        store = FlowObjectConstraintStore()
        key = (_ProdCB, _ConsCB, "buf")
        fn = lambda: None
        store.register_consumer(key, [fn])
        lst = store.consumer_constraints_for(key)
        lst.clear()
        assert store.consumer_constraints_for(key) == [fn]


# ---------------------------------------------------------------------------
# Tests: runtime — flow object randomization and binding lifecycle
# ---------------------------------------------------------------------------

class TestFlowObjectRandomization:
    def test_buffer_rand_fields_not_all_zero(self):
        """DataBuf.addr/.size should be randomized, not stuck at defaults."""
        for seed in range(5):
            _probe_results.clear()
            _run(ScenarioRunner(MyComp(), seed=seed).run(_ProbeTransfer))

        addrs = [v for k, v in _probe_results if k == "addr"]
        assert any(a != 0 for a in addrs), (
            f"All producer addr values were 0 across 5 seeds: {addrs}"
        )

    def test_no_rand_buffer_does_not_crash(self):
        """Buffer with no rand fields must not crash schedule execution."""
        _run(ScenarioRunner(MyComp(), seed=1).run(_NRTransfer))

    def test_consumer_sees_flow_object_in_body(self):
        """Consumer body() must receive the concrete flow object (not None)."""
        _cons_body_values.clear()
        _run(ScenarioRunner(MyComp(), seed=7).run(_XferCB))
        assert len(_cons_body_values) == 1
        assert _cons_body_values[0] is not None
        assert isinstance(_cons_body_values[0], DataBuf)

    def test_producer_sees_flow_object_in_pre_solve(self):
        """Producer pre_solve() must see the flow object (not None)."""
        _prod_pre_values.clear()
        _run(ScenarioRunner(MyComp(), seed=3).run(_XferPS))
        assert len(_prod_pre_values) == 1
        assert _prod_pre_values[0] is not None, "Producer.pre_solve() did not see the flow object"
        assert isinstance(_prod_pre_values[0], DataBuf)

    def test_producer_and_consumer_share_same_instance(self):
        """Producer and consumer must receive the exact same flow object."""
        _prod_bufs.clear()
        _cons_bufs.clear()
        _run(ScenarioRunner(MyComp(), seed=5).run(_XferSI))
        assert len(_prod_bufs) == 1 and len(_cons_bufs) == 1
        assert _prod_bufs[0] is _cons_bufs[0], (
            "Producer and consumer must share the same flow object instance"
        )

    def test_consumer_sees_flow_object_in_pre_solve(self):
        """Consumer pre_solve() must also see the concrete flow object."""
        _cons_pre_values.clear()
        _run(ScenarioRunner(MyComp(), seed=9).run(_XferCP))
        assert len(_cons_pre_values) == 1
        assert _cons_pre_values[0] is not None, "Consumer.pre_solve() did not see the flow object"

    def test_flow_object_values_consistent(self):
        """addr/size seen by producer must match those the consumer sees."""
        _prod_state.clear()
        _cons_state.clear()
        _run(ScenarioRunner(MyComp(), seed=11).run(_XferCV))
        assert _prod_state['addr'] == _cons_state['addr']
        assert _prod_state['size'] == _cons_state['size']
