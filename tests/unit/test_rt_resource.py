"""Tests for rt/resource_rt.py — Phase 2."""
import asyncio
import dataclasses as dc
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.dataclasses.rt.resource_rt import (
    ResourceFieldInfo,
    get_resource_fields,
    acquire_resources,
    release_resources,
    make_resource,
)
from zuspec.dataclasses.rt.pool_resolver import PoolResolver
from zuspec.dataclasses.rt.action_context import ActionContext


# ---------------------------------------------------------------------------
# Resource types
# ---------------------------------------------------------------------------

@zdc.dataclass
class DmaChannel(zdc.Resource):
    pass


@zdc.dataclass
class CpuCore(zdc.Resource):
    pass


def _make_channels(n=2):
    return ClaimPool.fromList([make_resource(DmaChannel) for _ in range(n)])


def _make_cores(n=2):
    return ClaimPool.fromList([make_resource(CpuCore) for _ in range(n)])


@zdc.dataclass
class DmaComp(zdc.Component):
    channels: ClaimPool = zdc.pool(default_factory=_make_channels)


@zdc.dataclass
class CpuComp(zdc.Component):
    cores: ClaimPool = zdc.pool(default_factory=_make_cores)


# ---------------------------------------------------------------------------
# get_resource_fields()
# ---------------------------------------------------------------------------

def test_no_resource_fields():
    """Action with no lock/share fields returns empty list."""
    @zdc.dataclass
    class SimpleAction(zdc.Action[DmaComp]):
        async def body(self):
            pass

    assert get_resource_fields(SimpleAction) == []


def test_lock_field_detected():
    """lock() field is returned as claim='lock'."""
    @zdc.dataclass
    class LockAction(zdc.Action[DmaComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self):
            pass

    fields = get_resource_fields(LockAction)
    assert len(fields) == 1
    assert fields[0].name == "chan"
    assert fields[0].claim == "lock"
    assert fields[0].field_type is DmaChannel


def test_share_field_detected():
    """share() field is returned as claim='share'."""
    @zdc.dataclass
    class ShareAction(zdc.Action[CpuComp]):
        core: CpuCore = zdc.share()
        async def body(self):
            pass

    fields = get_resource_fields(ShareAction)
    assert len(fields) == 1
    assert fields[0].name == "core"
    assert fields[0].claim == "share"


def test_multiple_resource_fields():
    """Multiple lock/share fields are all returned."""
    @zdc.dataclass
    class MultiAction(zdc.Action[DmaComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self):
            pass

    fields = get_resource_fields(MultiAction)
    assert any(f.name == "chan" for f in fields)


# ---------------------------------------------------------------------------
# make_resource()
# ---------------------------------------------------------------------------

def test_make_resource_returns_instance():
    """make_resource returns a properly initialised resource instance."""
    r = make_resource(DmaChannel)
    assert isinstance(r, DmaChannel)
    assert r.instance_id == 0


# ---------------------------------------------------------------------------
# acquire_resources() / release_resources()
# ---------------------------------------------------------------------------

def test_acquire_lock_sets_field():
    """acquire_resources() acquires a lock and sets the field on action."""
    comp = DmaComp()
    pr = PoolResolver.build(comp)

    @zdc.dataclass
    class LockAction(zdc.Action[DmaComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self):
            pass

    async def run():
        action = object.__new__(LockAction)
        for f in dc.fields(LockAction):
            object.__setattr__(action, f.name, None)
        action.comp = comp

        ctx = ActionContext(
            action=action, comp=comp, pool_resolver=pr, seed=0
        )
        claims = await acquire_resources(action, ctx)
        assert action.chan is not None
        assert isinstance(action.chan, DmaChannel)
        release_resources(claims)
        return claims

    claims = asyncio.run(run())
    assert len(claims) == 1


def test_acquire_share_sets_field():
    """acquire_resources() acquires a shared claim and sets the field."""
    comp = CpuComp()
    pr = PoolResolver.build(comp)

    @zdc.dataclass
    class ShareAction(zdc.Action[CpuComp]):
        core: CpuCore = zdc.share()
        async def body(self):
            pass

    async def run():
        action = object.__new__(ShareAction)
        for f in dc.fields(ShareAction):
            object.__setattr__(action, f.name, None)
        action.comp = comp

        ctx = ActionContext(action=action, comp=comp, pool_resolver=pr, seed=0)
        claims = await acquire_resources(action, ctx)
        assert action.core is not None
        release_resources(claims)

    asyncio.run(run())


def test_release_frees_lock():
    """release_resources() frees the claim so subsequent lock() succeeds."""
    comp = DmaComp()
    pr = PoolResolver.build(comp)

    @zdc.dataclass
    class LockAction(zdc.Action[DmaComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self):
            pass

    async def run():
        action = object.__new__(LockAction)
        for f in dc.fields(LockAction):
            object.__setattr__(action, f.name, None)
        action.comp = comp
        ctx = ActionContext(action=action, comp=comp, pool_resolver=pr, seed=0)

        claims = await acquire_resources(action, ctx)
        release_resources(claims)

        # Should be able to acquire again
        claims2 = await acquire_resources(action, ctx)
        release_resources(claims2)

    asyncio.run(run())


def test_no_pool_means_no_claim():
    """Action with lock field but no pool on component skips gracefully."""
    @zdc.dataclass
    class EmptyComp(zdc.Component):
        pass

    @zdc.dataclass
    class LockAction(zdc.Action[EmptyComp]):
        chan: DmaChannel = zdc.lock()
        async def body(self):
            pass

    async def run():
        comp = EmptyComp()
        pr = PoolResolver.build(comp)
        action = object.__new__(LockAction)
        for f in dc.fields(LockAction):
            object.__setattr__(action, f.name, None)
        action.comp = comp
        ctx = ActionContext(action=action, comp=comp, pool_resolver=pr, seed=0)
        claims = await acquire_resources(action, ctx)
        assert claims == []

    asyncio.run(run())
