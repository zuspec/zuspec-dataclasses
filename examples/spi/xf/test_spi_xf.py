#!/usr/bin/env python3
#****************************************************************************
# SPI Transfer-Function Model Test
# Demonstrates SpiInitiatorXF and SpiTargetXF connected via Transport
#****************************************************************************

import sys
sys.path.insert(0, '../../../src')

import asyncio
import zuspec.dataclasses as zdc
from typing import Tuple
from spi_model_xf import SpiInitiatorXF, SpiTargetXF


@zdc.dataclass
class SpiTarget(zdc.Component):
    """Simple SPI target that echoes received data with modifications."""
    sio : zdc.Transport[Tuple[zdc.u8, zdc.u128], zdc.u128] = zdc.export()
    
    # Statistics
    rx_count : int = zdc.field(default=0)
    last_data : int = zdc.field(default=0)
    
    def __bind__(self): return {
        self.sio : self.rx
    }
    
    def rx(self, args: Tuple[zdc.u8, zdc.u128]) -> zdc.u128:
        """Handle incoming SPI transfer - return complement of data."""
        tgt_sel, data = args
        self.rx_count += 1
        self.last_data = data
        # Return bitwise complement (simple loopback pattern)
        return (~data) & 0xFF  # Mask to 8 bits for simplicity


@zdc.dataclass
class SpiTestbench(zdc.Component):
    """Top-level testbench connecting SPI initiator and target."""
    initiator : SpiInitiatorXF = zdc.field()
    target : SpiTarget = zdc.field()
    
    # Test configuration
    num_transfers : int = zdc.field(default=1000)
    errors : int = zdc.field(default=0)
    
    def __bind__(self): return {
        self.initiator.sio : self.target.sio
    }
    
    async def run_test(self):
        """Run the SPI transfer test."""
        # Configure the initiator
        # 8-bit transfers, divider=1, target select=0
        await self.initiator.configure(
            char_len=8,
            divider=1,
            tgt_sel=0
        )
        
        print(f"Starting {self.num_transfers} SPI transfers...")
        print(f"Clock period: {self.initiator.clk_period}")
        
        start_time = self.time()
        
        for i in range(self.num_transfers):
            # Send incrementing pattern
            tx_data = i & 0xFF
            rx_data = await self.initiator.tx(tx_data)
            
            # Verify response (should be complement)
            expected = (~tx_data) & 0xFF
            if rx_data != expected:
                self.errors += 1
                if self.errors <= 5:  # Only print first 5 errors
                    print(f"  Error at transfer {i}: sent {tx_data:#04x}, "
                          f"got {rx_data:#04x}, expected {expected:#04x}")
        
        end_time = self.time()
        elapsed = end_time.amt - start_time.amt  # Assuming same units
        
        print(f"\nTest completed:")
        print(f"  Transfers: {self.num_transfers}")
        print(f"  Errors: {self.errors}")
        print(f"  Target RX count: {self.target.rx_count}")
        print(f"  Elapsed time: {end_time}")
        
        if self.errors == 0:
            print("  Result: PASS")
        else:
            print("  Result: FAIL")
        
        return self.errors == 0


def test_spi_xf_basic():
    """Basic test with default configuration."""
    print("\n=== SPI XF Basic Test ===")
    
    # Create the testbench - child components are created automatically
    tb = SpiTestbench(num_transfers=100)
    
    # Set the clock period on the initiator after construction
    tb.initiator.clk_period = zdc.Time.ns(10)
    
    result = asyncio.run(tb.run_test())
    assert result, "Test failed"
    tb.shutdown()


def test_spi_xf_fast_clock():
    """Test with faster clock (1ns period)."""
    print("\n=== SPI XF Fast Clock Test ===")
    
    tb = SpiTestbench(num_transfers=1000)
    tb.initiator.clk_period = zdc.Time.ns(1)
    
    result = asyncio.run(tb.run_test())
    assert result, "Test failed"
    tb.shutdown()


def test_spi_xf_slow_clock():
    """Test with slower clock (100ns period)."""
    print("\n=== SPI XF Slow Clock Test ===")
    
    tb = SpiTestbench(num_transfers=100)
    tb.initiator.clk_period = zdc.Time.ns(100)
    
    result = asyncio.run(tb.run_test())
    assert result, "Test failed"
    tb.shutdown()


def test_spi_xf_throughput():
    """Throughput test with many transfers."""
    print("\n=== SPI XF Throughput Test ===")
    import time as wall_time
    
    num_transfers = 5000
    
    tb = SpiTestbench(num_transfers=num_transfers)
    tb.initiator.clk_period = zdc.Time.ns(10)
    
    wall_start = wall_time.perf_counter()
    result = asyncio.run(tb.run_test())
    wall_end = wall_time.perf_counter()
    
    wall_elapsed = wall_end - wall_start
    transfers_per_sec = num_transfers / wall_elapsed
    
    print(f"\nPerformance metrics:")
    print(f"  Wall time: {wall_elapsed:.3f} seconds")
    print(f"  Throughput: {transfers_per_sec:,.0f} transfers/sec")
    
    assert result, "Test failed"
    tb.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("SPI Transfer-Function Model Tests")
    print("=" * 60)
    
    test_spi_xf_basic()
    test_spi_xf_fast_clock()
    test_spi_xf_slow_clock()
    test_spi_xf_throughput()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
