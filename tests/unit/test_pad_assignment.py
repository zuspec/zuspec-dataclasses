"""Pad assignment modeling pattern — integration test and performance benchmark.

Models the PSS pad_configuration pattern from modeling_patterns/pss/pad_configuration/:

  - 13 physical pads (A_PAD0..A_PAD4, B_PAD0..B_PAD6, RST_PAD)
  - SPI initiator interface: needs 5 pads (IN, OUT, CLK, SEL_0, SEL_1)
  - SPI target interface: needs 4 pads (IN, OUT, CLK, TGT_SEL)
  - Valid configurations (matching the PSS example):
      * 2 initiators  (initiator0 + initiator1)
      * initiator0 + target0
      * 2 targets     (target0 + target1)
  - All 13 pads live in one shared pool; each is locked exclusively to
    one interface — no two interfaces share a pad in the same solve.
  - Constrained acquisition: each lock field accepts only pads in its
    signal-specific valid set (the _resource_filters mechanism).

Performance characterization:
  - Baseline scenario (2 interfaces) timed over N iterations
  - Scaled scenario with a synthetically enlarged padring
"""
from __future__ import annotations

import asyncio
import enum
import time
from typing import Callable

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.dataclasses.rt.resource_rt import make_resource
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


# ---------------------------------------------------------------------------
# Pad IDs — mirror the CSV pad_info table (pad_id = pool index)
# ---------------------------------------------------------------------------

class PadId(enum.IntEnum):
    A_PAD0  = 0
    A_PAD1  = 1
    A_PAD2  = 2
    A_PAD3  = 3
    A_PAD4  = 4
    B_PAD0  = 5
    B_PAD1  = 6
    B_PAD2  = 7
    B_PAD3  = 8
    B_PAD4  = 9
    B_PAD5  = 10
    B_PAD6  = 11
    RST_PAD = 12

NUM_PADS = len(PadId)  # 13


# ---------------------------------------------------------------------------
# Valid pad sets per interface/signal — derived from the CSV pad_func_info table
# ---------------------------------------------------------------------------

# Each entry: frozenset of PadId int values legal for (interface, signal)
_VALID: dict[str, dict[str, frozenset]] = {
    "initiator0": {
        "SIG_IN":    frozenset({PadId.A_PAD0}),
        "SIG_OUT":   frozenset({PadId.A_PAD1}),
        "SIG_CLK":   frozenset({PadId.A_PAD2}),
        "SIG_SEL_0": frozenset({PadId.A_PAD3}),
        "SIG_SEL_1": frozenset({PadId.A_PAD4}),
    },
    "initiator1": {
        "SIG_IN":    frozenset({PadId.B_PAD0}),
        "SIG_OUT":   frozenset({PadId.B_PAD1}),
        "SIG_CLK":   frozenset({PadId.B_PAD2}),
        "SIG_SEL_0": frozenset({PadId.B_PAD3}),
        "SIG_SEL_1": frozenset({PadId.B_PAD4}),
    },
    "target0": {
        "SIG_IN":    frozenset({PadId.B_PAD0}),
        "SIG_OUT":   frozenset({PadId.B_PAD1}),
        "SIG_CLK":   frozenset({PadId.B_PAD2}),
        "SIG_TGT_SEL": frozenset({PadId.B_PAD5}),
    },
    "target1": {
        "SIG_IN":    frozenset({PadId.A_PAD0}),
        "SIG_OUT":   frozenset({PadId.A_PAD1}),
        "SIG_CLK":   frozenset({PadId.A_PAD2}),
        "SIG_TGT_SEL": frozenset({PadId.B_PAD6}),
    },
}


def _pad_filter(valid_ids: frozenset) -> Callable:
    """Return a resource-filter predicate for the given valid pad set."""
    return lambda r, _i, _v=valid_ids: r.pad_id in _v


# ---------------------------------------------------------------------------
# PadResource — one instance per physical pad in the padring pool
# ---------------------------------------------------------------------------

@zdc.dataclass
class PadResource(zdc.Resource):
    """Exclusive claim on one physical pad."""
    pad_id: int = 0  # int(PadId)


def _make_padring(n_pads: int = NUM_PADS) -> ClaimPool:
    """Build a ClaimPool of *n_pads* PadResource objects.

    For the baseline model n_pads=13 (one per physical pad).
    Scaled benchmarks pass a larger value to stress the solver's pool scan.
    """
    pads = []
    for i in range(n_pads):
        r = make_resource(PadResource)
        r.pad_id = i
        r.instance_id = i
        pads.append(r)
    return ClaimPool.fromList(pads)


# ---------------------------------------------------------------------------
# System component — owns the shared padring pool
# ---------------------------------------------------------------------------

@zdc.dataclass
class SpiSystem(zdc.Component):
    """Top-level component: shared padring pool for all SPI interfaces."""
    padring: ClaimPool = zdc.pool(default_factory=_make_padring)


# ---------------------------------------------------------------------------
# Per-instance SPI actions — one class per interface instance so the
# valid-pad sets are statically known (matching PSS per-component binding).
# Each class uses _resource_filters in pre_solve() to constrain which pads
# from the shared pool are eligible for each lock field.
# ---------------------------------------------------------------------------

# -- initiator0 ---------------------------------------------------------------

@zdc.dataclass
class Init0Configure(zdc.Action[SpiSystem]):
    """Configure 5 pads for SPI initiator0."""
    sig_in:    PadResource = zdc.lock()
    sig_out:   PadResource = zdc.lock()
    sig_clk:   PadResource = zdc.lock()
    sig_sel_0: PadResource = zdc.lock()
    sig_sel_1: PadResource = zdc.lock()
    _body_called: bool = False

    def pre_solve(self) -> None:
        vp = _VALID["initiator0"]
        self._resource_filters = {
            "sig_in":    _pad_filter(vp["SIG_IN"]),
            "sig_out":   _pad_filter(vp["SIG_OUT"]),
            "sig_clk":   _pad_filter(vp["SIG_CLK"]),
            "sig_sel_0": _pad_filter(vp["SIG_SEL_0"]),
            "sig_sel_1": _pad_filter(vp["SIG_SEL_1"]),
        }

    async def body(self) -> None:
        self._body_called = True


# -- initiator1 ---------------------------------------------------------------

@zdc.dataclass
class Init1Configure(zdc.Action[SpiSystem]):
    """Configure 5 pads for SPI initiator1."""
    sig_in:    PadResource = zdc.lock()
    sig_out:   PadResource = zdc.lock()
    sig_clk:   PadResource = zdc.lock()
    sig_sel_0: PadResource = zdc.lock()
    sig_sel_1: PadResource = zdc.lock()
    _body_called: bool = False

    def pre_solve(self) -> None:
        vp = _VALID["initiator1"]
        self._resource_filters = {
            "sig_in":    _pad_filter(vp["SIG_IN"]),
            "sig_out":   _pad_filter(vp["SIG_OUT"]),
            "sig_clk":   _pad_filter(vp["SIG_CLK"]),
            "sig_sel_0": _pad_filter(vp["SIG_SEL_0"]),
            "sig_sel_1": _pad_filter(vp["SIG_SEL_1"]),
        }

    async def body(self) -> None:
        self._body_called = True


# -- target0 ------------------------------------------------------------------

@zdc.dataclass
class Tgt0Configure(zdc.Action[SpiSystem]):
    """Configure 4 pads for SPI target0."""
    sig_in:      PadResource = zdc.lock()
    sig_out:     PadResource = zdc.lock()
    sig_clk:     PadResource = zdc.lock()
    sig_tgt_sel: PadResource = zdc.lock()
    _body_called: bool = False

    def pre_solve(self) -> None:
        vp = _VALID["target0"]
        self._resource_filters = {
            "sig_in":      _pad_filter(vp["SIG_IN"]),
            "sig_out":     _pad_filter(vp["SIG_OUT"]),
            "sig_clk":     _pad_filter(vp["SIG_CLK"]),
            "sig_tgt_sel": _pad_filter(vp["SIG_TGT_SEL"]),
        }

    async def body(self) -> None:
        self._body_called = True


# -- target1 ------------------------------------------------------------------

@zdc.dataclass
class Tgt1Configure(zdc.Action[SpiSystem]):
    """Configure 4 pads for SPI target1."""
    sig_in:      PadResource = zdc.lock()
    sig_out:     PadResource = zdc.lock()
    sig_clk:     PadResource = zdc.lock()
    sig_tgt_sel: PadResource = zdc.lock()
    _body_called: bool = False

    def pre_solve(self) -> None:
        vp = _VALID["target1"]
        self._resource_filters = {
            "sig_in":      _pad_filter(vp["SIG_IN"]),
            "sig_out":     _pad_filter(vp["SIG_OUT"]),
            "sig_clk":     _pad_filter(vp["SIG_CLK"]),
            "sig_tgt_sel": _pad_filter(vp["SIG_TGT_SEL"]),
        }

    async def body(self) -> None:
        self._body_called = True


# ---------------------------------------------------------------------------
# Compound actions — one per valid system configuration
# ---------------------------------------------------------------------------

@zdc.dataclass
class Config2Initiators(zdc.Action[SpiSystem]):
    """Scenario: initiator0 + initiator1 active simultaneously."""
    init0: Init0Configure = None
    init1: Init1Configure = None

    async def activity(self) -> None:
        with zdc.parallel():
            await self.init0()
            await self.init1()


@zdc.dataclass
class Config1Init1Target(zdc.Action[SpiSystem]):
    """Scenario: initiator0 + target0 active simultaneously."""
    init0: Init0Configure = None
    tgt0:  Tgt0Configure  = None

    async def activity(self) -> None:
        with zdc.parallel():
            await self.init0()
            await self.tgt0()


@zdc.dataclass
class Config2Targets(zdc.Action[SpiSystem]):
    """Scenario: target0 + target1 active simultaneously."""
    tgt0: Tgt0Configure = None
    tgt1: Tgt1Configure = None

    async def activity(self) -> None:
        with zdc.parallel():
            await self.tgt0()
            await self.tgt1()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Correctness tests
# ---------------------------------------------------------------------------

def test_2initiators_body_called():
    """Both initiator sub-actions execute their body."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=42).run(Config2Initiators))
    assert result.init0._body_called
    assert result.init1._body_called


def test_2initiators_valid_pads():
    """Each initiator's pads satisfy the valid-pad constraint from the CSV."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=42).run(Config2Initiators))

    vp0 = _VALID["initiator0"]
    assert result.init0.sig_in.pad_id    in vp0["SIG_IN"]
    assert result.init0.sig_out.pad_id   in vp0["SIG_OUT"]
    assert result.init0.sig_clk.pad_id   in vp0["SIG_CLK"]
    assert result.init0.sig_sel_0.pad_id in vp0["SIG_SEL_0"]
    assert result.init0.sig_sel_1.pad_id in vp0["SIG_SEL_1"]

    vp1 = _VALID["initiator1"]
    assert result.init1.sig_in.pad_id    in vp1["SIG_IN"]
    assert result.init1.sig_out.pad_id   in vp1["SIG_OUT"]
    assert result.init1.sig_clk.pad_id   in vp1["SIG_CLK"]
    assert result.init1.sig_sel_0.pad_id in vp1["SIG_SEL_0"]
    assert result.init1.sig_sel_1.pad_id in vp1["SIG_SEL_1"]


def test_2initiators_no_pad_conflicts():
    """All 10 assigned pads are distinct (exclusive lock semantics)."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=42).run(Config2Initiators))
    pads0 = [getattr(result.init0, s).pad_id
             for s in ('sig_in', 'sig_out', 'sig_clk', 'sig_sel_0', 'sig_sel_1')]
    pads1 = [getattr(result.init1, s).pad_id
             for s in ('sig_in', 'sig_out', 'sig_clk', 'sig_sel_0', 'sig_sel_1')]
    all_pads = pads0 + pads1
    assert len(all_pads) == len(set(all_pads)), f"Pad collision: {all_pads}"


def test_2initiators_pool_released():
    """After run, all pad claims are dropped — pool returns to fully free."""
    comp = SpiSystem()
    _run(ScenarioRunner(comp, seed=7).run(Config2Initiators))
    assert all(s == 0 for s in comp.padring._state), \
        f"Pool still locked: {comp.padring._state}"


def test_1init_1target_body_called():
    """initiator0 + target0 — both sub-actions execute."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=1).run(Config1Init1Target))
    assert result.init0._body_called
    assert result.tgt0._body_called


def test_1init_1target_valid_pads():
    """Initiator0 + target0 each get pads from their respective valid sets."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=1).run(Config1Init1Target))

    vpi = _VALID["initiator0"]
    assert result.init0.sig_in.pad_id    in vpi["SIG_IN"]
    assert result.init0.sig_out.pad_id   in vpi["SIG_OUT"]
    assert result.init0.sig_clk.pad_id   in vpi["SIG_CLK"]
    assert result.init0.sig_sel_0.pad_id in vpi["SIG_SEL_0"]
    assert result.init0.sig_sel_1.pad_id in vpi["SIG_SEL_1"]

    vpt = _VALID["target0"]
    assert result.tgt0.sig_in.pad_id      in vpt["SIG_IN"]
    assert result.tgt0.sig_out.pad_id     in vpt["SIG_OUT"]
    assert result.tgt0.sig_clk.pad_id     in vpt["SIG_CLK"]
    assert result.tgt0.sig_tgt_sel.pad_id in vpt["SIG_TGT_SEL"]


def test_1init_1target_no_pad_conflicts():
    """initiator0 + target0 — no shared pads (9 distinct pads total)."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=1).run(Config1Init1Target))
    pi = [getattr(result.init0, s).pad_id
          for s in ('sig_in', 'sig_out', 'sig_clk', 'sig_sel_0', 'sig_sel_1')]
    pt = [getattr(result.tgt0, s).pad_id
          for s in ('sig_in', 'sig_out', 'sig_clk', 'sig_tgt_sel')]
    all_pads = pi + pt
    assert len(all_pads) == len(set(all_pads)), f"Pad collision: {all_pads}"


def test_2targets_body_called():
    """target0 + target1 — both sub-actions execute."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=3).run(Config2Targets))
    assert result.tgt0._body_called
    assert result.tgt1._body_called


def test_2targets_valid_pads():
    """target0 + target1 each get pads from their respective valid sets."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=3).run(Config2Targets))

    vp0 = _VALID["target0"]
    assert result.tgt0.sig_in.pad_id      in vp0["SIG_IN"]
    assert result.tgt0.sig_out.pad_id     in vp0["SIG_OUT"]
    assert result.tgt0.sig_clk.pad_id     in vp0["SIG_CLK"]
    assert result.tgt0.sig_tgt_sel.pad_id in vp0["SIG_TGT_SEL"]

    vp1 = _VALID["target1"]
    assert result.tgt1.sig_in.pad_id      in vp1["SIG_IN"]
    assert result.tgt1.sig_out.pad_id     in vp1["SIG_OUT"]
    assert result.tgt1.sig_clk.pad_id     in vp1["SIG_CLK"]
    assert result.tgt1.sig_tgt_sel.pad_id in vp1["SIG_TGT_SEL"]


def test_2targets_no_pad_conflicts():
    """target0 + target1 — no shared pads (8 distinct pads total)."""
    comp = SpiSystem()
    result = _run(ScenarioRunner(comp, seed=3).run(Config2Targets))
    pt0 = [getattr(result.tgt0, s).pad_id
           for s in ('sig_in', 'sig_out', 'sig_clk', 'sig_tgt_sel')]
    pt1 = [getattr(result.tgt1, s).pad_id
           for s in ('sig_in', 'sig_out', 'sig_clk', 'sig_tgt_sel')]
    all_pads = pt0 + pt1
    assert len(all_pads) == len(set(all_pads)), f"Pad collision: {all_pads}"


def test_multi_seed_stability():
    """All three configurations run cleanly across 20 seeds."""
    for seed in range(20):
        for cls in (Config2Initiators, Config1Init1Target, Config2Targets):
            comp = SpiSystem()
            _run(ScenarioRunner(comp, seed=seed).run(cls))


def test_pool_released_all_configs():
    """Pool returns to fully-free state after each of the three configurations."""
    for action_cls in (Config2Initiators, Config1Init1Target, Config2Targets):
        comp = SpiSystem()
        _run(ScenarioRunner(comp, seed=42).run(action_cls))
        assert all(s == 0 for s in comp.padring._state), \
            f"{action_cls.__name__}: pool still locked: {comp.padring._state}"


# ---------------------------------------------------------------------------
# Performance benchmarks
# ---------------------------------------------------------------------------

def _time_n_runs(action_cls, n: int, pad_count: int = NUM_PADS) -> dict:
    """Run *action_cls* on a fresh SpiSystem *n* times; return timing stats."""
    t0 = time.perf_counter()
    for seed in range(n):
        comp = SpiSystem()
        comp.padring = _make_padring(pad_count)
        _run(ScenarioRunner(comp, seed=seed).run(action_cls))
    elapsed = time.perf_counter() - t0
    return {
        "action": action_cls.__name__,
        "pad_count": pad_count,
        "iterations": n,
        "total_s": elapsed,
        "per_iter_ms": elapsed / n * 1000,
        "throughput_per_s": n / elapsed,
    }


def test_perf_2initiators_baseline():
    """Perf: 2-initiator scenario, 13 pads, 100 iterations."""
    r = _time_n_runs(Config2Initiators, n=100, pad_count=13)
    print(f"\n[perf] {r['action']} pad_count={r['pad_count']} "
          f"n={r['iterations']}: "
          f"{r['per_iter_ms']:.3f} ms/iter  "
          f"{r['throughput_per_s']:.0f} iter/s")
    assert r['total_s'] < 30.0, f"Too slow: {r['total_s']:.1f}s for 100 iters"


def test_perf_1init_1target_baseline():
    """Perf: init0+target0 scenario, 13 pads, 100 iterations."""
    r = _time_n_runs(Config1Init1Target, n=100, pad_count=13)
    print(f"\n[perf] {r['action']} pad_count={r['pad_count']} "
          f"n={r['iterations']}: "
          f"{r['per_iter_ms']:.3f} ms/iter  "
          f"{r['throughput_per_s']:.0f} iter/s")
    assert r['total_s'] < 30.0


def test_perf_2targets_baseline():
    """Perf: 2-target scenario, 13 pads, 100 iterations."""
    r = _time_n_runs(Config2Targets, n=100, pad_count=13)
    print(f"\n[perf] {r['action']} pad_count={r['pad_count']} "
          f"n={r['iterations']}: "
          f"{r['per_iter_ms']:.3f} ms/iter  "
          f"{r['throughput_per_s']:.0f} iter/s")
    assert r['total_s'] < 30.0


def test_perf_scaling():
    """Perf: measure solve time vs padring size for the 2-initiator scenario.

    The valid-pad sets stay fixed (single valid pad per signal); only the
    pool search space grows.  This characterizes how ListClaimPool scan
    cost scales with n_pads.
    """
    results = []
    for pad_count in (13, 50, 100, 200, 500):
        r = _time_n_runs(Config2Initiators, n=50, pad_count=pad_count)
        results.append(r)
        print(f"\n[perf-scale] pad_count={pad_count:4d}  "
              f"{r['per_iter_ms']:.3f} ms/iter  "
              f"{r['throughput_per_s']:.0f} iter/s")

    worst = max(results, key=lambda r: r['total_s'])
    assert worst['total_s'] < 60.0, \
        f"Scaling scenario too slow: {worst['total_s']:.1f}s at pad_count={worst['pad_count']}"


# ---------------------------------------------------------------------------
# Standalone entry point — full benchmark table
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    N = 200
    print("\n" + "=" * 70)
    print("PAD ASSIGNMENT — PERFORMANCE CHARACTERIZATION")
    print("=" * 70)
    print()
    print(f"{'Scenario':<26} {'Pads':>5} {'N':>5} {'ms/iter':>10} {'iter/s':>10}")
    print("-" * 60)
    for cls, pads in [(Config2Initiators, 13), (Config1Init1Target, 13), (Config2Targets, 13)]:
        r = _time_n_runs(cls, n=N, pad_count=pads)
        print(f"{r['action']:<26} {r['pad_count']:>5} {r['iterations']:>5} "
              f"{r['per_iter_ms']:>10.3f} {r['throughput_per_s']:>10.0f}")

    print()
    print("Pool-size scaling (2-initiator config, 50 iters each):")
    print(f"{'Pad count':>10} {'ms/iter':>10} {'iter/s':>10}")
    print("-" * 35)
    for pad_count in (13, 50, 100, 200, 500, 1000):
        r = _time_n_runs(Config2Initiators, n=50, pad_count=pad_count)
        print(f"{pad_count:>10} {r['per_iter_ms']:>10.3f} {r['throughput_per_s']:>10.0f}")
    print()
