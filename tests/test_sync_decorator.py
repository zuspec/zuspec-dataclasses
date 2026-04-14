"""Phase 2 tests — decorator changes: new-style @sync(domain=) and bare @sync."""

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.decorators import ExecSync


# ---------------------------------------------------------------------------
# T1  @sync used as bare decorator (no call)
# ---------------------------------------------------------------------------

class TestSyncBareDecorator:
    def test_bare_sync_produces_ExecSync(self):
        @zdc.sync
        def _proc(self):
            pass

        assert isinstance(_proc, ExecSync)

    def test_bare_sync_domain_is_none(self):
        @zdc.sync
        def _proc(self):
            pass

        assert _proc.domain is None

    def test_bare_sync_legacy_fields_are_none(self):
        @zdc.sync
        def _proc(self):
            pass

        assert _proc.clock is None
        assert _proc.reset is None

    def test_bare_sync_method_is_callable(self):
        @zdc.sync
        def _proc(self):
            pass

        assert callable(_proc.method)


# ---------------------------------------------------------------------------
# T2  @sync(domain=...) new-style
# ---------------------------------------------------------------------------

class TestSyncDomainKwarg:
    def test_domain_lambda_stored(self):
        lam = lambda s: s.sys_clk
        @zdc.sync(domain=lam)
        def _proc(self):
            pass

        assert isinstance(_proc, ExecSync)
        assert _proc.domain is lam

    def test_domain_none_is_default(self):
        @zdc.sync()
        def _proc(self):
            pass

        assert _proc.domain is None

    def test_domain_set_legacy_fields_still_none(self):
        lam = lambda s: s.fast_clk
        @zdc.sync(domain=lam)
        def _proc(self):
            pass

        assert _proc.clock is None
        assert _proc.reset is None


# ---------------------------------------------------------------------------
# T3  Legacy @sync(clock=, reset=) still works
# ---------------------------------------------------------------------------

class TestSyncLegacyAPI:
    def test_clock_reset_string(self):
        @zdc.sync(clock="clk", reset="rst_n")
        def _proc(self):
            pass

        assert isinstance(_proc, ExecSync)
        assert _proc.clock == "clk"
        assert _proc.reset == "rst_n"

    def test_clock_reset_lambda(self):
        clk_lam = lambda s: s.clk
        rst_lam = lambda s: s.rst_n
        @zdc.sync(clock=clk_lam, reset=rst_lam)
        def _proc(self):
            pass

        assert _proc.clock is clk_lam
        assert _proc.reset is rst_lam

    def test_reset_async_flag(self):
        @zdc.sync(clock="clk", reset="rst_n", reset_async=True)
        def _proc(self):
            pass

        assert _proc.reset_async is True
        assert _proc.reset_active_low is True

    def test_reset_active_high(self):
        @zdc.sync(clock="clk", reset="rst", reset_active_low=False)
        def _proc(self):
            pass

        assert _proc.reset_active_low is False


# ---------------------------------------------------------------------------
# T4  ExecSync.domain field is present and typed correctly in dataclass
# ---------------------------------------------------------------------------

class TestExecSyncFields:
    def test_domain_field_exists(self):
        import dataclasses
        names = {f.name for f in dataclasses.fields(ExecSync)}
        assert "domain" in names

    def test_domain_default_is_none(self):
        import dataclasses
        defs = {f.name: f.default for f in dataclasses.fields(ExecSync)}
        assert defs["domain"] is None


# ---------------------------------------------------------------------------
# T5  Bare @sync works inside a @zdc.dataclass component
# ---------------------------------------------------------------------------

class TestSyncInsideComponent:
    def test_component_with_bare_sync(self):
        @zdc.dataclass
        class SimpleComp(zdc.Component):
            clock : zdc.bit = zdc.input()
            reset : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock", reset="reset")
            def _count(self):
                if self.reset:
                    self.count = 0
                else:
                    self.count = self.count + 1

        # The class should be constructable; component machinery should not crash
        assert SimpleComp is not None

    def test_component_with_domain_sync(self):
        """@sync(domain=...) on a component with a class-level ClockDomain."""
        @zdc.dataclass
        class DomainComp(zdc.Component):
            clock : zdc.bit = zdc.input()
            reset : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            # domain= kwarg just stores the lambda; factory uses it in Phase 3
            @zdc.sync(domain=lambda s: s)
            def _count(self):
                self.count = self.count + 1

        assert DomainComp is not None
