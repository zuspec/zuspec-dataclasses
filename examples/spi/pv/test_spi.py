#!/usr/bin/env python3
#****************************************************************************
# SPI Master Core Test
# Tests the SPI register model and byte transfer operations
#****************************************************************************

import sys
sys.path.insert(0, '../../../src')

import asyncio
import zuspec.dataclasses as zdc
from spi_model import SpiMaster, SpiRegs, SpiCtrl


def test_spi_registers_basic():
    """Test basic register read/write operations."""
    print("\n=== Test: SPI Registers Basic ===")
    
    @zdc.dataclass
    class Top(zdc.Component):
        spi : SpiMaster = zdc.field()
        
        async def run(self):
            # Test writing to control register using integer value
            # Bit layout: char_len[6:0]=8, tx_neg[10]=1, ass[13]=1
            ctrl_val = 8 | (1 << 10) | (1 << 13)
            
            await self.spi.regs.ctrl.write(ctrl_val)
            ctrl_read = await self.spi.regs.ctrl.read()
            
            assert ctrl_read.char_len == 8, f"char_len mismatch: {ctrl_read.char_len}"
            assert ctrl_read.tx_neg == 1, f"tx_neg mismatch: {ctrl_read.tx_neg}"
            assert ctrl_read.ass == 1, f"ass mismatch: {ctrl_read.ass}"
            print("  CTRL register read/write: PASS")
            
            # Test writing to data register
            await self.spi.regs.data0.write(0xAB)
            data_read = await self.spi.regs.data0.read()
            assert data_read == 0xAB, f"data0 mismatch: {data_read:#x}"
            print("  DATA0 register read/write: PASS")
            
            # Test slave select register (write integer, read struct)
            ss_val = 0x04  # Select slave 2
            await self.spi.regs.ss.write(ss_val)
            ss_read = await self.spi.regs.ss.read()
            assert ss_read.ss == 0x04, f"ss mismatch: {ss_read.ss:#x}"
            print("  SS register read/write: PASS")
            
            # Test divider register  
            div_val = 0x000A  # Divider = 10
            await self.spi.regs.divider.write(div_val)
            div_read = await self.spi.regs.divider.read()
            assert div_read.divider == 0x000A, f"divider mismatch: {div_read.divider:#x}"
            print("  DIVIDER register read/write: PASS")
            
            print("  All basic register tests PASSED")
    
    t = Top()
    asyncio.run(t.run())
    t.shutdown()


def test_spi_send_byte():
    """Test sending a byte over SPI."""
    print("\n=== Test: SPI Send Byte ===")
    
    @zdc.dataclass
    class Top(zdc.Component):
        spi : SpiMaster = zdc.field()
        
        async def run(self):
            # Set up divider for faster simulation (write as integer)
            await self.spi.regs.divider.write(1)
            
            # Send a byte
            print("  Sending byte 0x55 to slave 0...")
            rx_data = await self.spi.send_byte(0x55, slave_select=0)
            print(f"  Received byte: {rx_data:#04x}")
            
            # Verify the transfer completed (GO_BSY should be 0)
            is_busy = await self.spi.is_busy()
            assert not is_busy, "SPI should not be busy after transfer"
            print("  Transfer completed successfully")
            
            # Send another byte to slave 2
            print("  Sending byte 0xAA to slave 2...")
            rx_data = await self.spi.send_byte(0xAA, slave_select=2)
            print(f"  Received byte: {rx_data:#04x}")
            
            print("  SPI send byte test PASSED")
    
    t = Top()
    asyncio.run(t.run())
    t.shutdown()


def test_spi_multiple_transfers():
    """Test multiple consecutive SPI transfers."""
    print("\n=== Test: SPI Multiple Transfers ===")
    
    @zdc.dataclass
    class Top(zdc.Component):
        spi : SpiMaster = zdc.field()
        
        async def run(self):
            # Set up divider (write as integer)
            await self.spi.regs.divider.write(1)
            
            # Send a sequence of bytes
            test_data = [0x01, 0x02, 0x03, 0x04, 0x55, 0xAA, 0xFF, 0x00]
            
            print(f"  Sending {len(test_data)} bytes...")
            for i, byte in enumerate(test_data):
                await self.spi.send_byte(byte, slave_select=0)
                print(f"    Byte {i}: sent {byte:#04x}")
            
            print("  Multiple transfers test PASSED")
    
    t = Top()
    asyncio.run(t.run())
    t.shutdown()


def test_spi_memmap_access():
    """Test SPI register access through memory-mapped address space."""
    print("\n=== Test: SPI Memory-Mapped Access ===")
    
    @zdc.dataclass
    class Top(zdc.Component):
        spi : SpiMaster = zdc.field()
        asp : zdc.AddressSpace = zdc.field()
        
        def __bind__(self): return {
            self.asp.mmap : (
                zdc.At(0x0, self.spi.regs)
            )
        }
        
        async def run(self):
            hndl = self.asp.base
            
            # Write to data0 register (offset 0x00)
            print("  Writing 0x12345678 to data0 via address space...")
            await hndl.write32(0x00, 0x12345678)
            
            # Read back
            data = await hndl.read32(0x00)
            assert data == 0x12345678, f"data0 read mismatch: {data:#x}"
            print(f"  Read back: {data:#010x} - PASS")
            
            # Write to CTRL register (offset 0x10)
            # Set char_len=8, tx_neg=1, ass=1 => bit pattern
            # char_len[6:0] = 8, tx_neg[10] = 1, ass[13] = 1
            ctrl_val = 8 | (1 << 10) | (1 << 13)
            print(f"  Writing {ctrl_val:#010x} to CTRL via address space...")
            await hndl.write32(0x10, ctrl_val)
            
            # Read back CTRL
            ctrl_read = await hndl.read32(0x10)
            print(f"  Read back CTRL: {ctrl_read:#010x}")
            
            # Verify individual bits
            char_len = ctrl_read & 0x7F
            tx_neg = (ctrl_read >> 10) & 1
            ass = (ctrl_read >> 13) & 1
            
            assert char_len == 8, f"char_len mismatch: {char_len}"
            assert tx_neg == 1, f"tx_neg mismatch: {tx_neg}"
            assert ass == 1, f"ass mismatch: {ass}"
            print("  CTRL register bits verified - PASS")
            
            # Write to DIVIDER register (offset 0x14)
            print("  Writing 0x000A to DIVIDER via address space...")
            await hndl.write32(0x14, 0x000A)
            
            div_read = await hndl.read32(0x14)
            assert div_read == 0x000A, f"divider read mismatch: {div_read:#x}"
            print(f"  Read back DIVIDER: {div_read:#010x} - PASS")
            
            # Write to SS register (offset 0x18)
            print("  Writing 0x04 to SS via address space...")
            await hndl.write32(0x18, 0x04)  # Select slave 2
            
            ss_read = await hndl.read32(0x18)
            assert ss_read == 0x04, f"ss read mismatch: {ss_read:#x}"
            print(f"  Read back SS: {ss_read:#010x} - PASS")
            
            print("  Memory-mapped access test PASSED")
    
    t = Top()
    asyncio.run(t.run())
    t.shutdown()


def test_spi_full_transfer_via_regs():
    """Test a complete SPI transfer by programming registers directly."""
    print("\n=== Test: SPI Full Transfer via Registers ===")
    
    @zdc.dataclass 
    class Top(zdc.Component):
        spi : SpiMaster = zdc.field()
        asp : zdc.AddressSpace = zdc.field()
        
        def __bind__(self): return {
            self.asp.mmap : (
                zdc.At(0x0, self.spi.regs)
            )
        }
        
        async def run(self):
            hndl = self.asp.base
            
            print("  Programming SPI for 8-bit transfer...")
            
            # Step 1: Set divider
            await hndl.write32(0x14, 0x0001)  # Fast divider for simulation
            print("    Set DIVIDER = 1")
            
            # Step 2: Write transmit data
            await hndl.write32(0x00, 0x5A)  # Transmit 0x5A
            print("    Set TX data = 0x5A")
            
            # Step 3: Set slave select
            await hndl.write32(0x18, 0x01)  # Select slave 0
            print("    Set SS = 0x01 (slave 0)")
            
            # Step 4: Configure CTRL and start transfer
            # char_len=8, go_bsy=1, tx_neg=1, ass=1
            ctrl_val = 8 | (1 << 8) | (1 << 10) | (1 << 13)
            await hndl.write32(0x10, ctrl_val)
            print(f"    Set CTRL = {ctrl_val:#010x} (8-bit, GO, TX_NEG, ASS)")
            
            # Step 5: Wait for transfer to complete (poll GO_BSY)
            print("    Polling for transfer completion...")
            poll_count = 0
            max_polls = 100
            while poll_count < max_polls:
                ctrl_read = await hndl.read32(0x10)
                go_bsy = (ctrl_read >> 8) & 1
                if go_bsy == 0:
                    print(f"    Transfer complete after {poll_count + 1} polls")
                    break
                await self.wait(zdc.Time.ns(10))
                poll_count += 1
            
            if poll_count >= max_polls:
                raise AssertionError("Transfer did not complete in time")
            
            # Step 6: Read received data
            rx_data = await hndl.read32(0x00)
            print(f"    Received data: {rx_data:#010x}")
            
            print("  Full transfer via registers test PASSED")
    
    t = Top()
    asyncio.run(t.run())
    t.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("SPI Master Core Model Tests")
    print("=" * 60)
    
    test_spi_registers_basic()
    test_spi_send_byte()
    test_spi_multiple_transfers()
    test_spi_memmap_access()
    test_spi_full_transfer_via_regs()
    
    print("\n" + "=" * 60)
    print("All tests PASSED!")
    print("=" * 60)
