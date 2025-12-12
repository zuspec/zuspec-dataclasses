import asyncio
import zuspec.dataclasses as zdc
from typing import Annotated, SupportsInt


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

def test_memmap_structreg_write():

    @zdc.dataclass
    class RegA(zdc.PackedStruct):
        en : zdc.uint1_t = zdc.field()

    @zdc.dataclass
    class Regs(zdc.RegFile):
        a : zdc.Reg[RegA] = zdc.field()
        b : zdc.Reg[zdc.uint32_t] = zdc.field()
        c : zdc.Reg[zdc.uint32_t] = zdc.field()

    @zdc.dataclass
    class Device(zdc.Component):
        regs : Regs = zdc.field()
        expected_vals : list = zdc.field(default_factory=list)
        errors : list = zdc.field(default_factory=list)

        @zdc.process
        async def _poll(self):
            while True:
                av = await self.regs.a.read()
                bv = await self.regs.b.read()
                cv = await self.regs.c.read()

                # Check against expected values if any
                if self.expected_vals:
                    exp_a, exp_b, exp_c = self.expected_vals[-1]
                    if av.en != exp_a:
                        self.errors.append(f"Time {self.time()}: a.en={av.en}, expected {exp_a}")
                    if bv != exp_b:
                        self.errors.append(f"Time {self.time()}: b={bv:#010x}, expected {exp_b:#010x}")
                    if cv != exp_c:
                        self.errors.append(f"Time {self.time()}: c={cv:#010x}, expected {exp_c:#010x}")

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
            hndl = self.asp.base

            # Write to register a (offset 0x0) - packed struct with en bit
            await hndl.write32(0x0, 1)
            self.d.expected_vals.append((1, 0, 0))  # en=1, b=0, c=0
            await self.wait(zdc.Time.ns(50))
            
            # Write to register b (offset 0x4)
            await hndl.write32(0x4, 0x12345678)
            self.d.expected_vals.append((1, 0x12345678, 0))  # en=1, b=0x12345678, c=0
            await self.wait(zdc.Time.ns(50))
            
            # Write to register c (offset 0x8)
            await hndl.write32(0x8, 0xABCDEF00)
            self.d.expected_vals.append((1, 0x12345678, 0xABCDEF00))  # en=1, b=0x12345678, c=0xABCDEF00
            await self.wait(zdc.Time.ns(50))
            
            # Write to register a again - toggle en to 0 (value 2 has bit 0 = 0)
            await hndl.write32(0x0, 2)
            self.d.expected_vals.append((0, 0x12345678, 0xABCDEF00))  # en=0, b=0x12345678, c=0xABCDEF00
            await self.wait(zdc.Time.ns(50))
            
            # Write to register a again - toggle en to 1 (value 3 has bit 0 = 1)
            await hndl.write32(0x0, 3)
            self.d.expected_vals.append((1, 0x12345678, 0xABCDEF00))  # en=1, b=0x12345678, c=0xABCDEF00
            await self.wait(zdc.Time.ns(50))
            
            # Write to all registers with different values
            await hndl.write32(0x0, 0)  # en=0
            await hndl.write32(0x4, 0xDEADBEEF)
            await hndl.write32(0x8, 0xCAFEBABE)
            self.d.expected_vals.append((0, 0xDEADBEEF, 0xCAFEBABE))
            await self.wait(zdc.Time.ns(50))
            
            # Check for errors
            if self.d.errors:
                print("\nTest FAILED with errors:")
                for err in self.d.errors:
                    print(f"  {err}")
                raise AssertionError(f"Test failed with {len(self.d.errors)} errors")
            else:
                print("\nTest PASSED: All register values matched expected values")

    t = Top()

    asyncio.run(t.run())
    


