#!/usr/bin/env python3
#****************************************************************************
# SPI Software Interface Test
# Tests the SPI register model defined in sw_if.py
#****************************************************************************

import sys
sys.path.insert(0, '../../src')

import asyncio
import zuspec.dataclasses as zdc
from sw_if import SpiRegs, SpiCtrl, SpiDivider, SpiSS


def test_spi_ctrl_register():
    """Test SpiCtrl packed struct definition."""
    print("\n=== Test: SpiCtrl Register ===")
    
    # Verify the dataclass is defined
    import dataclasses as dc
    assert dc.is_dataclass(SpiCtrl), "SpiCtrl should be a dataclass"
    
    # Verify fields exist
    field_names = {f.name for f in dc.fields(SpiCtrl)}
    assert 'char_len' in field_names
    assert 'go_bsy' in field_names
    assert 'rx_neg' in field_names
    assert 'tx_neg' in field_names
    assert 'lsb' in field_names
    assert 'ie' in field_names
    assert 'ass' in field_names
    
    print("  SpiCtrl structure verified")
    print("  Fields: char_len, go_bsy, rx_neg, tx_neg, lsb, ie, ass")
    print("  PASS")


def test_spi_divider_register():
    """Test SpiDivider packed struct definition."""
    print("\n=== Test: SpiDivider Register ===")
    
    import dataclasses as dc
    assert dc.is_dataclass(SpiDivider), "SpiDivider should be a dataclass"
    
    field_names = {f.name for f in dc.fields(SpiDivider)}
    assert 'divider' in field_names
    assert 'reserved' in field_names
    
    print("  SpiDivider structure verified")
    print("  Fields: divider, reserved")
    print("  PASS")


def test_spi_ss_register():
    """Test SpiSS packed struct definition."""
    print("\n=== Test: SpiSS Register ===")
    
    import dataclasses as dc
    assert dc.is_dataclass(SpiSS), "SpiSS should be a dataclass"
    
    field_names = {f.name for f in dc.fields(SpiSS)}
    assert 'ss' in field_names
    
    print("  SpiSS structure verified")
    print("  Fields: ss")
    print("  PASS")


def test_spi_regs_structure():
    """Test SpiRegs register file structure."""
    print("\n=== Test: SpiRegs Structure ===")
    
    @zdc.dataclass
    class TestComponent(zdc.Component):
        regs : SpiRegs = zdc.field()
    
    comp = TestComponent()
    
    # Verify all registers exist
    assert hasattr(comp.regs, 'data0')
    assert hasattr(comp.regs, 'data1')
    assert hasattr(comp.regs, 'data2')
    assert hasattr(comp.regs, 'data3')
    assert hasattr(comp.regs, 'ctrl')
    assert hasattr(comp.regs, 'divider')
    assert hasattr(comp.regs, 'ss')
    
    print("  SpiRegs register file verified")
    print("  Registers: data0, data1, data2, data3, ctrl, divider, ss")
    print("  PASS")
    
    comp.shutdown()


def test_spi_regs_read_write():
    """Test reading and writing SPI registers."""
    print("\n=== Test: SpiRegs Read/Write ===")
    
    @zdc.dataclass
    class TestComponent(zdc.Component):
        regs : SpiRegs = zdc.field()
        
        async def test_registers(self):
            # Test data registers
            await self.regs.data0.write(0x12345678)
            val = await self.regs.data0.read()
            assert val == 0x12345678, f"data0 mismatch: {val:#x}"
            print("  data0 read/write: PASS")
            
            await self.regs.data1.write(0xABCDEF00)
            val = await self.regs.data1.read()
            assert val == 0xABCDEF00, f"data1 mismatch: {val:#x}"
            print("  data1 read/write: PASS")
            
            # Test CTRL register with packed struct
            ctrl_val = (8 | (1 << 10) | (1 << 13))  # char_len=8, tx_neg=1, ass=1
            await self.regs.ctrl.write(ctrl_val)
            ctrl = await self.regs.ctrl.read()
            assert ctrl.char_len == 8, f"char_len mismatch: {ctrl.char_len}"
            assert ctrl.tx_neg == 1, f"tx_neg mismatch: {ctrl.tx_neg}"
            assert ctrl.ass == 1, f"ass mismatch: {ctrl.ass}"
            print("  ctrl read/write: PASS")
            
            # Test DIVIDER register
            div_val = 0x0010
            await self.regs.divider.write(div_val)
            div = await self.regs.divider.read()
            assert div.divider == 0x0010, f"divider mismatch: {div.divider:#x}"
            print("  divider read/write: PASS")
            
            # Test SS register
            ss_val = 0x04  # Select slave 2
            await self.regs.ss.write(ss_val)
            ss = await self.regs.ss.read()
            assert ss.ss == 0x04, f"ss mismatch: {ss.ss:#x}"
            print("  ss read/write: PASS")
    
    comp = TestComponent()
    asyncio.run(comp.test_registers())
    comp.shutdown()


def test_spi_regs_memory_mapped():
    """Test SPI registers through memory-mapped address space."""
    print("\n=== Test: SpiRegs Memory-Mapped Access ===")
    
    @zdc.dataclass
    class TestComponent(zdc.Component):
        regs : SpiRegs = zdc.field()
        asp : zdc.AddressSpace = zdc.field()
        
        def __bind__(self): return {
            self.asp.mmap : zdc.At(0x1000, self.regs)
        }
        
        async def test_memmap(self):
            hndl = self.asp.base
            
            # Write to data0 at offset 0x1000
            await hndl.write32(0x1000, 0xDEADBEEF)
            val = await hndl.read32(0x1000)
            assert val == 0xDEADBEEF, f"data0 mismatch: {val:#x}"
            print(f"  data0 @ 0x1000: {val:#010x} - PASS")
            
            # Write to ctrl at offset 0x1010
            ctrl_val = (16 | (1 << 8) | (1 << 12))  # char_len=16, go_bsy=1, ie=1
            await hndl.write32(0x1010, ctrl_val)
            val = await hndl.read32(0x1010)
            assert (val & 0x7F) == 16, f"char_len mismatch"
            assert ((val >> 8) & 1) == 1, f"go_bsy mismatch"
            assert ((val >> 12) & 1) == 1, f"ie mismatch"
            print(f"  ctrl @ 0x1010: {val:#010x} - PASS")
            
            # Write to divider at offset 0x1014
            await hndl.write32(0x1014, 0x000A)
            val = await hndl.read32(0x1014)
            assert (val & 0xFFFF) == 0x000A, f"divider mismatch: {val:#x}"
            print(f"  divider @ 0x1014: {val:#010x} - PASS")
            
            # Write to ss at offset 0x1018
            await hndl.write32(0x1018, 0x01)  # Select slave 0
            val = await hndl.read32(0x1018)
            assert (val & 0xFF) == 0x01, f"ss mismatch: {val:#x}"
            print(f"  ss @ 0x1018: {val:#010x} - PASS")
    
    comp = TestComponent()
    asyncio.run(comp.test_memmap())
    comp.shutdown()


def test_register_offsets():
    """Test that register offsets match the specification."""
    print("\n=== Test: Register Offset Verification ===")
    
    @zdc.dataclass
    class TestComponent(zdc.Component):
        regs : SpiRegs = zdc.field()
        asp : zdc.AddressSpace = zdc.field()
        
        def __bind__(self): return {
            self.asp.mmap : zdc.At(0x0, self.regs)
        }
        
        async def test_offsets(self):
            hndl = self.asp.base
            
            # According to spec:
            # 0x00 - data0 (Rx0/Tx0)
            # 0x04 - data1 (Rx1/Tx1)
            # 0x08 - data2 (Rx2/Tx2)
            # 0x0C - data3 (Rx3/Tx3)
            # 0x10 - ctrl
            # 0x14 - divider
            # 0x18 - ss
            
            # Write unique values to each register
            await hndl.write32(0x00, 0x00000000)
            await hndl.write32(0x04, 0x11111111)
            await hndl.write32(0x08, 0x22222222)
            await hndl.write32(0x0C, 0x33333333)
            await hndl.write32(0x10, 0x44)
            await hndl.write32(0x14, 0x55)
            await hndl.write32(0x18, 0x66)
            
            # Read back and verify
            assert await hndl.read32(0x00) == 0x00000000
            assert await hndl.read32(0x04) == 0x11111111
            assert await hndl.read32(0x08) == 0x22222222
            assert await hndl.read32(0x0C) == 0x33333333
            assert (await hndl.read32(0x10) & 0x7F) == 0x44
            assert (await hndl.read32(0x14) & 0xFFFF) == 0x55
            assert (await hndl.read32(0x18) & 0xFF) == 0x66
            
            print("  Register offsets verified:")
            print("    0x00 - data0")
            print("    0x04 - data1")
            print("    0x08 - data2")
            print("    0x0C - data3")
            print("    0x10 - ctrl")
            print("    0x14 - divider")
            print("    0x18 - ss")
            print("  PASS")
    
    comp = TestComponent()
    asyncio.run(comp.test_offsets())
    comp.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("SPI Software Interface Tests")
    print("=" * 60)
    
    test_spi_ctrl_register()
    test_spi_divider_register()
    test_spi_ss_register()
    test_spi_regs_structure()
    test_spi_regs_read_write()
    test_spi_regs_memory_mapped()
    test_register_offsets()
    
    print("\n" + "=" * 60)
    print("All tests PASSED!")
    print("=" * 60)
