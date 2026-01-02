import asyncio
import pytest
import zuspec.dataclasses as zdc


def test_bundle():
    """Test bundle(), mirror(), and const() directionality plus clock/reset binding."""

    @zdc.dataclass
    class ReqRsp(zdc.Struct):
        DATA_WIDTH: zdc.uint32_t = zdc.const(default=32)
        req: zdc.bv = zdc.output(width=lambda s:s.DATA_WIDTH)
        rsp: zdc.bv = zdc.input(width=lambda s:s.DATA_WIDTH)

    @zdc.dataclass
    class Prod(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        io: ReqRsp = zdc.bundle()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _tick(self):
            if self.reset:
                self.io.req = 0
            else:
                self.io.req = self.io.req + 1

    @zdc.dataclass
    class Cons(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        tick_cnt: zdc.uint32_t = zdc.field(default=0)
        io: ReqRsp = zdc.mirror()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _tick(self):
            if self.reset:
                self.tick_cnt = 0
            else:
                self.tick_cnt = self.tick_cnt + 1

        # Read producer request and drive a modified response
        # Note: since this is sync logic with deferred-assignment semantics,
        # rsp will trail req by one clock.
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _rsp(self):
            if self.reset:
                self.io.rsp = 0
            else:
                self.io.rsp = self.io.req + 2

    @zdc.dataclass
    class Top(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        prod: Prod = zdc.inst()
        cons: Cons = zdc.inst()

        # Ensure eval infrastructure is initialized so signal bindings propagate
        @zdc.comb
        def _noop(self):
            pass

        def __bind__(self):
            # Order matters: bind clock to consumer first so it samples req
            # before the producer updates it on the same edge.
            return (
                (self.cons.clock, self.clock),
                (self.cons.reset, self.reset),
                (self.prod.clock, self.clock),
                (self.prod.reset, self.reset),
                (self.prod.io, self.cons.io),
            )

    top = Top()

    assert top.prod.io is not top.cons.io
    assert top.prod.io.DATA_WIDTH == 32

    async def tick():
        top.clock = 1
        await top.wait(zdc.Time.delta())
        top.clock = 0
        await top.wait(zdc.Time.delta())

    async def run():
        # NOTE: at top-level, signals may only be driven from async context.
        # Propagation occurs when we call wait().

        top.clock = 0
        top.reset = 1
        await top.wait(zdc.Time.delta())

        # While in reset, a clock edge should keep outputs at reset values
        await tick()
        assert top.prod.io.req == 0
        assert top.cons.io.req == 0
        assert top.cons.io.rsp == 0
        assert top.prod.io.rsp == 0
        assert top.cons.tick_cnt == 0

        # Release reset and run a few cycles
        top.reset = 0
        await top.wait(zdc.Time.delta())

        for i in range(3):
            await tick()
            exp_req = (i+1)
            assert top.prod.io.req == exp_req
            assert top.cons.io.req == exp_req
            exp_rsp = exp_req + 1
            assert top.cons.io.rsp == exp_rsp
            assert top.prod.io.rsp == exp_rsp
            assert top.cons.tick_cnt == exp_req

        # Directionality checks (still enforced)
        with pytest.raises(AttributeError):
            top.prod.io.rsp = 0x1
        with pytest.raises(AttributeError):
            top.cons.io.req = 0x2

    asyncio.run(run())

def test_bundle_signal_bind():
    """Test bundle(), mirror(), and const() directionality plus clock/reset binding."""

    @zdc.dataclass
    class ReqRsp(zdc.Struct):
        DATA_WIDTH: zdc.uint32_t = zdc.const(default=32)
        req: zdc.bv = zdc.output(width=lambda s:s.DATA_WIDTH)
        rsp: zdc.bv = zdc.input(width=lambda s:s.DATA_WIDTH)

    @zdc.dataclass
    class Prod(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        io: ReqRsp = zdc.bundle()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _tick(self):
            if self.reset:
                self.io.req = 0
            else:
                self.io.req = self.io.req + 1

    @zdc.dataclass
    class Data(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        req : zdc.u32 = zdc.input()
        rsp : zdc.u32 = zdc.output()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _rsp(self):
            if self.reset:
                self.rsp = 0
            else:
                self.rsp = self.req + 2

    @zdc.dataclass
    class Cons(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        tick_cnt: zdc.uint32_t = zdc.field(default=0)
        io: ReqRsp = zdc.mirror()
        _dat : Data = zdc.inst()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _tick(self):
            if self.reset:
                self.tick_cnt = 0
            else:
                self.tick_cnt = self.tick_cnt + 1

        def __bind__(self): return (
            (self.clock, self._dat.clock),
            (self.reset, self._dat.reset),
            (self.io.req, self._dat.req),
            (self.io.rsp, self._dat.rsp),
        )

        # Read producer request and drive a modified response
        # Note: since this is sync logic with deferred-assignment semantics,
        # rsp will trail req by one clock.

    @zdc.dataclass
    class Top(zdc.Component):
        clock: zdc.bit = zdc.input()
        reset: zdc.bit = zdc.input()
        prod: Prod = zdc.inst()
        cons: Cons = zdc.inst()

        # Ensure eval infrastructure is initialized so signal bindings propagate
        @zdc.comb
        def _noop(self):
            pass

        def __bind__(self):
            # Order matters: bind clock to consumer first so it samples req
            # before the producer updates it on the same edge.
            return (
                (self.cons.clock, self.clock),
                (self.cons.reset, self.reset),
                (self.prod.clock, self.clock),
                (self.prod.reset, self.reset),
                (self.prod.io, self.cons.io),
            )

    top = Top()

    assert top.prod.io is not top.cons.io
    assert top.prod.io.DATA_WIDTH == 32

    async def tick():
        top.clock = 1
        await top.wait(zdc.Time.delta())
        top.clock = 0
        await top.wait(zdc.Time.delta())

    async def run():
        # NOTE: at top-level, signals may only be driven from async context.
        # Propagation occurs when we call wait().

        top.clock = 0
        top.reset = 1
        await top.wait(zdc.Time.delta())

        # While in reset, a clock edge should keep outputs at reset values
        await tick()
        assert top.prod.io.req == 0
        assert top.cons.io.req == 0
        assert top.cons.io.rsp == 0
        assert top.prod.io.rsp == 0
        assert top.cons.tick_cnt == 0

        # Release reset and run a few cycles
        top.reset = 0
        await top.wait(zdc.Time.delta())

        for i in range(3):
            await tick()
            exp_req = (i+1)
            assert top.prod.io.req == exp_req
            assert top.cons.io.req == exp_req
            exp_rsp = exp_req + 1
            assert top.cons.io.rsp == exp_rsp
            assert top.prod.io.rsp == exp_rsp
            assert top.cons.tick_cnt == exp_req

        # Directionality checks (still enforced)
        with pytest.raises(AttributeError):
            top.prod.io.rsp = 0x1
        with pytest.raises(AttributeError):
            top.cons.io.req = 0x2

    asyncio.run(run())


if __name__ == "__main__":
    test_bundle()
    print("\n✓ test_bundle passed!")
