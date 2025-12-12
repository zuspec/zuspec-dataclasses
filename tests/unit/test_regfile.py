import asyncio
import zuspec.dataclasses as zdc
from typing import Annotated, SupportsInt

def test_smoke():
    @zdc.dataclass
    class Reg1(zdc.PackedStruct):
        en : Annotated[int, 1] = zdc.field()
        mode : Annotated[int, 3] = zdc.field()

    @zdc.dataclass
    class Regs(zdc.RegFile):
        r : zdc.Reg[Reg1] = zdc.field()


    regs : Regs = Regs()

    v = asyncio.run(regs.r.read())

    sum = int(v) + 2

    # Need to have some control over specifying
    # how physical memories map to byte-oriented
    # memory map
    # - We're effectively specifying a memory view in reverse




    @zdc.dataclass
    class MyC():
        # One implementation is that 'RegFile' provides 
        regs : Regs = zdc.field()
        mmap : zdc.MemoryMap = zdc.field()

        def __bind__(self): return {
            self.mmap : [
                zdc.At(0x2000, self.regs),
            ], 
        }

        @zdc.process
        async def _run(self):

            # Optimizable loop using events
            while True:
                val = await self.regs.r.read()
                if val.en:
                    break


    @zdc.dataclass
    class MyP(zdc.Component):
        p : zdc.MemIF = zdc.port()

        @zdc.process
        async def _run(self):
            await self.p.write32(10, 10)

    @zdc.dataclass
    class Top(zdc.Component):
        p : MyP = zdc.field()
        c : MyC = zdc.field()
        _aspace : zdc.AddressSpace = zdc.field()

        def __bind__(self): return {
            self._aspace : [
                zdc.At(0x00000000, self.c.mmap)
            ],
            self.p.p : self._aspace
        }

def test_local_mem():

    @zdc.dataclass
    class Top(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=1024)

        def run(self):
            self.mem.write(0, 25)
            assert self.mem.read(0) == 25

    t = Top()
    t.run()

def test_mem_access():

    @zdc.dataclass
    class Device(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=1024) # Need a 'size' option here?

        @zdc.process
        async def _run(self):
            while True:
                val = self.mem.read(0)
                print("val: 0x%08x" % val)
                await self.wait(zdc.Time.ns(10))

    @zdc.dataclass
    class Top(zdc.Component):
        dev : Device = zdc.field()
        aspace : zdc.AddressSpace = zdc.field()

        def __bind__(self): return {
            self.aspace.mmap : (
                zdc.At(0x00000000, self.dev.mem)
            )
        }

        async def run(self):
            hndl = self.aspace.base
            for i in range(16):
                await hndl.write32(4*i, i+1)
                await self.wait(zdc.Time.ns(100))

    t = Top()

    asyncio.run(t.run())

def test_memmap_reg_write():

    @zdc.dataclass
    class Regs(zdc.RegFile):
        a : zdc.Reg[zdc.uint32_t] = zdc.field()
        b : zdc.Reg[zdc.uint32_t] = zdc.field()
        c : zdc.Reg[zdc.uint32_t] = zdc.field()

    @zdc.dataclass
    class Device(zdc.Component):
        regs : Regs = zdc.field()

        @zdc.process
        async def _poll(self):
            while True:
                av = await self.regs.a.read()
                bv = await self.regs.b.read()
                cv = await self.regs.c.read()

                print("av: 0x%08x ; bv: 0x%08x ; cv: 0x%08x" % (av, bv, cv))

                await self.wait(zdc.Time.ns(10))

    @zdc.dataclass
    class Top(zdc.Component):
        d : Device = zdc.field()
        asp : zdc.AddressSpace = zdc.field()

        def __bind__(self): return {
            self.asp.mmap : (
                zdc.At(0x0, self.d.regs)
            )
        }

        async def run(self):
            print("--> run")
            hndl = self.asp.base

            await hndl.write32(0, 1)
            await self.wait(zdc.Time.ns(100))
            print("-- time:", self.time())
            await hndl.write32(0, 2)
            await self.wait(zdc.Time.ns(100))
            print("-- time:", self.time())
            await hndl.write32(0, 3)
            await self.wait(zdc.Time.ns(100))
            print("<-- run time:", self.time())

    t = Top()

    asyncio.run(t.run())

    


