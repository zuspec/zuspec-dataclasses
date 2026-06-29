"""Model classes used by test_local_func_inline.py.

Must live in a real .py file so DataModelFactory can getsource() them.
"""

import zuspec.dataclasses as zdc

MASK32 = 0xFFFF_FFFF


# ---------------------------------------------------------------------------
# SingleReturnComp — single-expression return value
# ---------------------------------------------------------------------------

@zdc.dataclass
class SingleReturnComp(zdc.Component):
    result: zdc.u32 = zdc.field(default=0)

    @zdc.proc
    async def _run(self):
        def double(x): return x + x
        y: int = 0
        y = double(5)
        while True:
            self.result = y
            await self.wait(zdc.Time.ns(1))


# ---------------------------------------------------------------------------
# VoidSideEffectComp — void function used as a statement
# ---------------------------------------------------------------------------

@zdc.dataclass
class VoidSideEffectComp(zdc.Component):
    counter: zdc.u32 = zdc.field(default=0)

    @zdc.proc
    async def _run(self):
        def bump(x): self.counter = self.counter + x
        while True:
            bump(1)
            await self.wait(zdc.Time.ns(1))


# ---------------------------------------------------------------------------
# ClosureOverOuterComp — local func captures an outer local variable
# ---------------------------------------------------------------------------

@zdc.dataclass
class ClosureOverOuterComp(zdc.Component):
    result: zdc.u32 = zdc.field(default=0)

    @zdc.proc
    async def _run(self):
        base: int = 10
        def add_base(x): return x + base
        while True:
            self.result = add_base(5)
            await self.wait(zdc.Time.ns(1))


# ---------------------------------------------------------------------------
# NestedLocalCallComp — Rs1() calls R(rs1) (two levels of local inlining)
# ---------------------------------------------------------------------------

@zdc.dataclass
class NestedLocalCallComp(zdc.Component):
    gpr: zdc.IndexedRegFile[zdc.u5, zdc.u32] = zdc.indexed_regfile(
        read_ports=2, write_ports=1
    )
    result: zdc.u32 = zdc.field(default=0)

    def __post_init__(self):
        from zuspec.be.py.rt.indexed_regfile_rt import IndexedRegFileRT
        if self.gpr is None:
            self.gpr = IndexedRegFileRT(depth=32, read_ports=2, write_ports=1)

    @zdc.proc
    async def _run(self):
        rs1: int = 1
        def R(idx): return self.gpr.get(idx) & MASK32
        def Rs1():  return R(rs1)
        while True:
            self.result = Rs1()
            await self.wait(zdc.Time.ns(1))


# ---------------------------------------------------------------------------
# NeverCalledComp — local def captured but never called (should not error)
# ---------------------------------------------------------------------------

@zdc.dataclass
class NeverCalledComp(zdc.Component):
    result: zdc.u32 = zdc.field(default=0)

    @zdc.proc
    async def _run(self):
        def unused(x): return x * 2  # never called
        while True:
            self.result = 42
            await self.wait(zdc.Time.ns(1))


# ---------------------------------------------------------------------------
# AsyncPureComp — async def with no await should be treated as pure
# ---------------------------------------------------------------------------

@zdc.dataclass
class AsyncPureComp(zdc.Component):
    result: zdc.u32 = zdc.field(default=0)

    @zdc.proc
    async def _run(self):
        async def pure_async(x): return x + 1
        while True:
            self.result = pure_async(7)
            await self.wait(zdc.Time.ns(1))
