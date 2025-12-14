#!/usr/bin/env python3
#****************************************************************************
# SPI Transfer-Function Model Performance Benchmark
# Measures maximum throughput for various transfer configurations
#****************************************************************************

import sys
sys.path.insert(0, '../../../src')

import asyncio
import time as wall_time
import zuspec.dataclasses as zdc
from typing import Tuple
from spi_model_xf import SpiInitiatorXF, SpiTargetXF


@zdc.dataclass
class SpiTarget(zdc.Component):
    """Simple SPI target for benchmarking."""
    sio : zdc.Transport[Tuple[zdc.uint8_t, zdc.uint128_t], zdc.uint128_t] = zdc.export()
    
    rx_count : int = zdc.field(default=0)
    
    def __bind__(self): return {
        self.sio : self.rx
    }
    
    def rx(self, args: Tuple[zdc.uint8_t, zdc.uint128_t]) -> zdc.uint128_t:
        """Handle incoming SPI transfer."""
        self.rx_count += 1
        tgt_sel, data = args
        return (~data) & 0xFF


@zdc.dataclass
class SpiBenchmark(zdc.Component):
    """Performance benchmark component."""
    initiator : SpiInitiatorXF = zdc.field()
    target : SpiTarget = zdc.field()
    
    num_transfers : int = zdc.field(default=10000)
    
    def __bind__(self): return {
        self.initiator.sio : self.target.sio
    }
    
    async def run_benchmark(self):
        """Run the benchmark and return metrics."""
        # Configure the initiator
        await self.initiator.configure(
            char_len=8,
            divider=1,
            tgt_sel=0
        )
        
        # Run transfers
        for i in range(self.num_transfers):
            tx_data = i & 0xFF
            await self.initiator.tx(tx_data)
        
        return {
            'transfers': self.num_transfers,
            'sim_time': self.time(),
            'rx_count': self.target.rx_count
        }


def run_single_benchmark(name, num_transfers, clock_period_ns):
    """Run a single benchmark configuration."""
    print(f"\n{'='*70}")
    print(f"Benchmark: {name}")
    print(f"  Transfers: {num_transfers:,}")
    print(f"  Clock Period: {clock_period_ns}ns")
    print(f"{'='*70}")
    
    # Create benchmark
    bench = SpiBenchmark(num_transfers=num_transfers)
    bench.initiator.clk_period = zdc.Time.ns(clock_period_ns)
    
    # Measure wall-clock time
    wall_start = wall_time.perf_counter()
    results = asyncio.run(bench.run_benchmark())
    wall_end = wall_time.perf_counter()
    
    # Calculate metrics
    wall_elapsed = wall_end - wall_start
    transfers_per_sec = num_transfers / wall_elapsed
    sim_time_ns = results['sim_time'].amt if hasattr(results['sim_time'], 'amt') else 0
    
    print(f"\nResults:")
    print(f"  Wall-clock time: {wall_elapsed:.4f} seconds")
    print(f"  Throughput: {transfers_per_sec:,.0f} transfers/sec")
    print(f"  Simulation time: {sim_time_ns:,.0f} ns")
    print(f"  Target RX count: {results['rx_count']:,}")
    print(f"  Transfers verified: {'PASS' if results['rx_count'] == num_transfers else 'FAIL'}")
    
    bench.shutdown()
    
    return {
        'name': name,
        'num_transfers': num_transfers,
        'clock_period_ns': clock_period_ns,
        'wall_time': wall_elapsed,
        'throughput': transfers_per_sec,
        'sim_time_ns': sim_time_ns
    }


def print_summary(all_results):
    """Print summary table of all benchmarks."""
    print(f"\n{'='*70}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*70}")
    print(f"{'Benchmark':<30} {'Transfers':<12} {'Wall Time':<12} {'Throughput':<15}")
    print(f"{'-'*70}")
    
    for r in all_results:
        print(f"{r['name']:<30} {r['num_transfers']:<12,} {r['wall_time']:<12.4f} {r['throughput']:>14,.0f}/s")
    
    print(f"{'='*70}")
    
    # Find best and worst
    best = max(all_results, key=lambda x: x['throughput'])
    worst = min(all_results, key=lambda x: x['throughput'])
    
    print(f"\nBest throughput: {best['name']} - {best['throughput']:,.0f} transfers/sec")
    print(f"Worst throughput: {worst['name']} - {worst['throughput']:,.0f} transfers/sec")
    print(f"Speedup ratio: {best['throughput']/worst['throughput']:.2f}x")


def main():
    print("="*70)
    print("SPI TRANSFER-FUNCTION MODEL PERFORMANCE BENCHMARK")
    print("="*70)
    print(f"Python asyncio-based simulation")
    print(f"Measuring transactions per second for various configurations")
    
    all_results = []
    
    # Benchmark 1: Small transfer count, fast clock
    all_results.append(run_single_benchmark(
        "Small/Fast (1K @ 1ns)",
        num_transfers=1000,
        clock_period_ns=1
    ))
    
    # Benchmark 2: Small transfer count, slow clock
    all_results.append(run_single_benchmark(
        "Small/Slow (1K @ 100ns)",
        num_transfers=1000,
        clock_period_ns=100
    ))
    
    # Benchmark 3: Medium transfer count, medium clock
    all_results.append(run_single_benchmark(
        "Medium/Medium (10K @ 10ns)",
        num_transfers=10000,
        clock_period_ns=10
    ))
    
    # Benchmark 4: Large transfer count, fast clock
    all_results.append(run_single_benchmark(
        "Large/Fast (50K @ 1ns)",
        num_transfers=50000,
        clock_period_ns=1
    ))
    
    # Benchmark 5: Large transfer count, medium clock
    all_results.append(run_single_benchmark(
        "Large/Medium (50K @ 10ns)",
        num_transfers=50000,
        clock_period_ns=10
    ))
    
    # Benchmark 6: Large transfer count, slow clock
    all_results.append(run_single_benchmark(
        "Large/Slow (50K @ 100ns)",
        num_transfers=50000,
        clock_period_ns=100
    ))
    
    # Benchmark 7: Very large transfer count
    all_results.append(run_single_benchmark(
        "Very Large (100K @ 10ns)",
        num_transfers=100000,
        clock_period_ns=10
    ))
    
    # Benchmark 8: Stress test - maximum throughput
    all_results.append(run_single_benchmark(
        "Stress Test (200K @ 1ns)",
        num_transfers=200000,
        clock_period_ns=1
    ))
    
    # Print summary
    print_summary(all_results)
    
    # Save results to file
    import json
    timestamp = wall_time.strftime("%Y%m%d_%H%M%S")
    filename = f"benchmark_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'results': all_results
        }, f, indent=2)
    
    print(f"\nResults saved to: {filename}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
    except Exception as e:
        print(f"\n\nError during benchmark: {e}")
        import traceback
        traceback.print_exc()
