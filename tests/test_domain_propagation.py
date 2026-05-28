"""Phase 3 — domain propagation tests.

Verifies that clock edges on a parent's domain propagate through the component
hierarchy so that child/grandchild @zdc.sync methods fire automatically.
"""

import asyncio
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Component classes used across tests
# ---------------------------------------------------------------------------

@zdc.dataclass
class PropLeaf(zdc.SyncComponent):
    """Simple counter — no CLK/RST ports; driven by parent domain."""
    reset_domain = zdc.ResetDomain(style="none")
    count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync
    def _inc(self):
        self.count = self.count + 1


@zdc.dataclass
class PropParent(zdc.SyncComponent):
    reset_domain = zdc.ResetDomain(style="none")
    leaf: PropLeaf = zdc.inst()


@zdc.dataclass
class PropGrandChild(zdc.SyncComponent):
    reset_domain = zdc.ResetDomain(style="none")
    count: zdc.bit32 = zdc.output(reset=0)

    @zdc.sync
    def _inc(self):
        self.count = self.count + 1


@zdc.dataclass
class PropChild(zdc.SyncComponent):
    reset_domain = zdc.ResetDomain(style="none")
    gc: PropGrandChild = zdc.inst()


@zdc.dataclass
class PropRoot3(zdc.SyncComponent):
    reset_domain = zdc.ResetDomain(style="none")
    child: PropChild = zdc.inst()


# ---------------------------------------------------------------------------
# Test: domain_children populated during elaboration
# ---------------------------------------------------------------------------

class TestDomainChildrenElaboration:
    def test_parent_has_leaf_in_domain_children(self):
        async def _run():
            async with zdc.simulate(PropParent) as p:
                children = p._impl._domain_children
                assert len(children) == 1
                assert children[0] is p.leaf

        asyncio.run(_run())

    def test_three_level_domain_children(self):
        async def _run():
            async with zdc.simulate(PropRoot3) as r:
                # Root has 'child' in its domain_children
                assert len(r._impl._domain_children) == 1
                assert r._impl._domain_children[0] is r.child
                # Child has 'gc' in its domain_children
                assert len(r.child._impl._domain_children) == 1
                assert r.child._impl._domain_children[0] is r.child.gc

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: clock edge propagates to child
# ---------------------------------------------------------------------------

class TestClockEdgePropagation:
    def test_parent_tick_advances_child_counter(self):
        async def _run():
            async with zdc.simulate(PropParent) as p:
                assert p.leaf.count == 0
                await p.domain.tick(5)
                assert p.leaf.count == 5

        asyncio.run(_run())

    def test_parent_tick_single_step(self):
        async def _run():
            async with zdc.simulate(PropParent) as p:
                await p.domain.tick(1)
                assert p.leaf.count == 1

        asyncio.run(_run())

    def test_three_level_propagation(self):
        async def _run():
            async with zdc.simulate(PropRoot3) as r:
                await r.domain.tick(7)
                assert r.child.gc.count == 7

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test: resolved domain attributes set on instances
# ---------------------------------------------------------------------------

class TestResolvedDomainAttributes:
    def test_resolved_clock_domain_set_on_parent(self):
        async def _run():
            async with zdc.simulate(PropParent) as p:
                resolved = getattr(p, '_zdc_resolved_clock_domain', None)
                assert resolved is not None

        asyncio.run(_run())

    def test_resolved_clock_domain_inherited_by_child(self):
        async def _run():
            async with zdc.simulate(PropParent) as p:
                parent_clk = getattr(p, '_zdc_resolved_clock_domain', None)
                leaf_clk = getattr(p.leaf, '_zdc_resolved_clock_domain', None)
                assert leaf_clk is not None
                # Both should reference the same underlying clock domain
                assert type(leaf_clk) is type(parent_clk)

        asyncio.run(_run())

    def test_resolved_reset_domain_inherited_by_child(self):
        async def _run():
            async with zdc.simulate(PropParent) as p:
                leaf_rst = getattr(p.leaf, '_zdc_resolved_reset_domain', None)
                assert leaf_rst is not None

        asyncio.run(_run())

    def test_three_level_resolved_clock_propagates(self):
        async def _run():
            async with zdc.simulate(PropRoot3) as r:
                for comp in [r, r.child, r.child.gc]:
                    clk = getattr(comp, '_zdc_resolved_clock_domain', None)
                    assert clk is not None, f"{type(comp).__name__} missing resolved clock domain"

        asyncio.run(_run())
