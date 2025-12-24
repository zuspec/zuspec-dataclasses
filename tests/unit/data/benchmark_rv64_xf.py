#!/usr/bin/env python3
"""
Performance benchmark for the RV64I Transfer-Function Level Model

This script measures the instruction throughput (instructions per second)
of the RV64I model under various workloads.
"""

import sys
sys.path.insert(0, '../../../src')

import asyncio
import time
import zuspec.dataclasses as zdc
from typing import Dict
from rv64_xf import Rv64XF


class SimpleMem:
    """Simple memory implementation for benchmarking."""
    
    def __init__(self):
        self._mem: Dict[int, int] = {}
    
    def load_program(self, addr: int, program: list):
        """Load a list of 32-bit instructions into memory."""
        for i, instr in enumerate(program):
            self._write32_sync(addr + i * 4, instr)
    
    def _write32_sync(self, addr: int, data: int):
        for i in range(4):
            self._mem[addr + i] = (data >> (i * 8)) & 0xFF
    
    async def read8(self, addr: int) -> int:
        return self._mem.get(addr, 0) & 0xFF
    
    async def read16(self, addr: int) -> int:
        lo = self._mem.get(addr, 0) & 0xFF
        hi = self._mem.get(addr + 1, 0) & 0xFF
        return (hi << 8) | lo
    
    async def read32(self, addr: int) -> int:
        result = 0
        for i in range(4):
            result |= (self._mem.get(addr + i, 0) & 0xFF) << (i * 8)
        return result
    
    async def read64(self, addr: int) -> int:
        result = 0
        for i in range(8):
            result |= (self._mem.get(addr + i, 0) & 0xFF) << (i * 8)
        return result
    
    async def write8(self, addr: int, data: int):
        self._mem[addr] = data & 0xFF
    
    async def write16(self, addr: int, data: int):
        self._mem[addr] = data & 0xFF
        self._mem[addr + 1] = (data >> 8) & 0xFF
    
    async def write32(self, addr: int, data: int):
        for i in range(4):
            self._mem[addr + i] = (data >> (i * 8)) & 0xFF
    
    async def write64(self, addr: int, data: int):
        for i in range(8):
            self._mem[addr + i] = (data >> (i * 8)) & 0xFF


# Instruction encoding helpers
def encode_r_type(opcode, rd, funct3, rs1, rs2, funct7):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_i_type(opcode, rd, funct3, rs1, imm):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_b_type(opcode, funct3, rs1, rs2, imm):
    imm_12 = (imm >> 12) & 1
    imm_10_5 = (imm >> 5) & 0x3F
    imm_4_1 = (imm >> 1) & 0xF
    imm_11 = (imm >> 11) & 1
    return (imm_12 << 31) | (imm_10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm_4_1 << 8) | (imm_11 << 7) | opcode

def encode_j_type(opcode, rd, imm):
    imm_20 = (imm >> 20) & 1
    imm_10_1 = (imm >> 1) & 0x3FF
    imm_11 = (imm >> 11) & 1
    imm_19_12 = (imm >> 12) & 0xFF
    return (imm_20 << 31) | (imm_10_1 << 21) | (imm_11 << 20) | (imm_19_12 << 12) | (rd << 7) | opcode

def encode_s_type(opcode, funct3, rs1, rs2, imm):
    imm_11_5 = (imm >> 5) & 0x7F
    imm_4_0 = imm & 0x1F
    return (imm_11_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm_4_0 << 7) | opcode


# Opcodes
OP_OP_IMM = 0x13
OP_OP = 0x33
OP_BRANCH = 0x63
OP_JAL = 0x6F
OP_LOAD = 0x03
OP_STORE = 0x23
EBREAK = 0x00100073


@zdc.dataclass
class BenchHarness(zdc.Component):
    """Benchmark harness for RV64I model."""
    cpu: Rv64XF = zdc.field()
    mem: SimpleMem = zdc.field(default_factory=SimpleMem)
    
    def __bind__(self):
        return {
            self.cpu.memif: self.mem
        }


def create_tight_loop_program(iterations: int):
    """Create a tight loop that counts down from iterations to 0.
    
    This measures raw instruction execution speed with minimal memory access.
    """
    # x1 = counter (starts at iterations)
    # Loop: decrement x1, branch if not zero
    program = [
        # Load iterations into x1 using lui + addi
        # lui x1, upper_bits
        # addi x1, x1, lower_bits
        ((iterations >> 12) << 12) | (1 << 7) | 0x37,  # lui x1, upper
        encode_i_type(OP_OP_IMM, 1, 0, 1, iterations & 0xFFF),  # addi x1, x1, lower
        # loop:
        encode_i_type(OP_OP_IMM, 1, 0, 1, -1 & 0xFFF),  # addi x1, x1, -1
        encode_b_type(OP_BRANCH, 1, 1, 0, -4 & 0x1FFF),  # bne x1, x0, loop (-4)
        EBREAK
    ]
    return program


def create_alu_intensive_program(iterations: int):
    """Create a program with heavy ALU operations.
    
    This measures ALU throughput with various arithmetic operations.
    """
    # For large iterations, use lui + addi to load the counter
    upper = (iterations >> 12) & 0xFFFFF
    lower = iterations & 0xFFF
    # Sign-extend lower if it would be treated as negative
    if lower >= 0x800:
        upper += 1
        lower = lower - 0x1000
    
    program = [
        # Initialize counter using lui + addi for large values
        (upper << 12) | (1 << 7) | 0x37,        # lui x1, upper
        encode_i_type(OP_OP_IMM, 1, 0, 1, lower & 0xFFF),  # addi x1, x1, lower
        encode_i_type(OP_OP_IMM, 2, 0, 0, 1),    # addi x2, x0, 1
        encode_i_type(OP_OP_IMM, 3, 0, 0, 2),    # addi x3, x0, 2
        encode_i_type(OP_OP_IMM, 4, 0, 0, 3),    # addi x4, x0, 3
        # loop: (8 ALU operations per iteration)
        encode_r_type(OP_OP, 5, 0, 2, 3, 0),     # add x5, x2, x3
        encode_r_type(OP_OP, 6, 0, 4, 5, 0x20),  # sub x6, x4, x5
        encode_r_type(OP_OP, 7, 4, 5, 6, 0),     # xor x7, x5, x6
        encode_r_type(OP_OP, 8, 6, 6, 7, 0),     # or x8, x6, x7
        encode_r_type(OP_OP, 9, 7, 7, 8, 0),     # and x9, x7, x8
        encode_r_type(OP_OP, 2, 0, 5, 6, 0),     # add x2, x5, x6
        encode_r_type(OP_OP, 3, 0, 7, 8, 0),     # add x3, x7, x8
        encode_r_type(OP_OP, 4, 0, 8, 9, 0),     # add x4, x8, x9
        encode_i_type(OP_OP_IMM, 1, 0, 1, -1 & 0xFFF),  # addi x1, x1, -1
        encode_b_type(OP_BRANCH, 1, 1, 0, -36 & 0x1FFF),  # bne x1, x0, loop (-36 bytes = -9 instructions)
        EBREAK
    ]
    return program


def create_memory_intensive_program(iterations: int):
    """Create a program with memory load/store operations.
    
    This measures memory access throughput.
    """
    # For large iterations, use lui + addi to load the counter
    upper = (iterations >> 12) & 0xFFFFF
    lower = iterations & 0xFFF
    if lower >= 0x800:
        upper += 1
        lower = lower - 0x1000
    
    program = [
        # x1 = counter, x10 = base address for data
        (upper << 12) | (1 << 7) | 0x37,        # lui x1, upper
        encode_i_type(OP_OP_IMM, 1, 0, 1, lower & 0xFFF),  # addi x1, x1, lower
        # lui x10, 0x3000 (data area at 0x3000000)
        (0x3000 << 12) | (10 << 7) | 0x37,
        encode_i_type(OP_OP_IMM, 2, 0, 0, 0x55), # addi x2, x0, 0x55 (pattern)
        # loop: store and load sequence
        encode_s_type(OP_STORE, 2, 10, 2, 0),    # sw x2, 0(x10)
        encode_i_type(OP_LOAD, 3, 2, 10, 0),     # lw x3, 0(x10)
        encode_s_type(OP_STORE, 2, 10, 3, 4),    # sw x3, 4(x10)
        encode_i_type(OP_LOAD, 4, 2, 10, 4),     # lw x4, 4(x10)
        encode_i_type(OP_OP_IMM, 1, 0, 1, -1 & 0xFFF),  # addi x1, x1, -1
        encode_b_type(OP_BRANCH, 1, 1, 0, -20 & 0x1FFF),  # bne x1, x0, loop (-20 bytes)
        EBREAK
    ]
    return program


def create_fibonacci_program(n: int):
    """Create a program that computes Fibonacci numbers.
    
    This is a realistic mixed workload with branches, arithmetic, and data movement.
    """
    # For large n, use lui + addi
    upper = (n >> 12) & 0xFFFFF
    lower = n & 0xFFF
    if lower >= 0x800:
        upper += 1
        lower = lower - 0x1000
    
    program = [
        (upper << 12) | (1 << 7) | 0x37,        # lui x1, upper
        encode_i_type(OP_OP_IMM, 1, 0, 1, lower & 0xFFF),  # addi x1, x1, lower (n)
        encode_i_type(OP_OP_IMM, 2, 0, 0, 0),    # addi x2, x0, 0  (fib(0))
        encode_i_type(OP_OP_IMM, 3, 0, 0, 1),    # addi x3, x0, 1  (fib(1))
        encode_i_type(OP_OP_IMM, 5, 0, 0, 2),    # addi x5, x0, 2  (counter)
        # loop:
        encode_b_type(OP_BRANCH, 4, 1, 5, 24),   # blt x1, x5, exit (+24 bytes)
        encode_r_type(OP_OP, 4, 0, 2, 3, 0),     # add x4, x2, x3
        encode_r_type(OP_OP, 2, 0, 3, 0, 0),     # add x2, x3, x0
        encode_r_type(OP_OP, 3, 0, 4, 0, 0),     # add x3, x4, x0
        encode_i_type(OP_OP_IMM, 5, 0, 5, 1),    # addi x5, x5, 1
        encode_j_type(OP_JAL, 0, -20 & 0x1FFFFF),# jal x0, loop
        # exit:
        EBREAK
    ]
    return program


async def run_benchmark(name: str, program: list, expected_instrs: int, warmup_runs: int = 2, bench_runs: int = 5):
    """Run a benchmark and report results."""
    
    harness = BenchHarness()
    harness.cpu.reset_v = 0x1000
    harness.mem.load_program(0x1000, program)
    
    # Warmup runs
    for _ in range(warmup_runs):
        harness.cpu.reset()
        await harness.cpu.run(max_instructions=expected_instrs + 1000)
    
    # Benchmark runs
    times = []
    instr_counts = []
    
    for _ in range(bench_runs):
        harness.cpu.reset()
        
        start_time = time.perf_counter()
        count = await harness.cpu.run(max_instructions=expected_instrs + 1000)
        end_time = time.perf_counter()
        
        times.append(end_time - start_time)
        instr_counts.append(count)
    
    # Calculate statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    avg_instrs = sum(instr_counts) / len(instr_counts)
    
    ips = avg_instrs / avg_time if avg_time > 0 else 0
    
    print(f"\n{name}")
    print(f"  Instructions executed: {int(avg_instrs):,}")
    print(f"  Time (avg/min/max): {avg_time*1000:.2f} / {min_time*1000:.2f} / {max_time*1000:.2f} ms")
    print(f"  Throughput: {ips:,.0f} instructions/sec ({ips/1e6:.2f} MIPS)")
    
    return ips, avg_instrs


async def main():
    print("=" * 70)
    print("RV64I Transfer-Function Model Performance Benchmark")
    print("=" * 70)
    
    results = []
    
    # Test 1: Tight loop (branch + decrement)
    iterations = 100000
    program = create_tight_loop_program(iterations)
    expected = 2 + iterations * 2  # init + (decrement + branch) * iterations
    ips, count = await run_benchmark(
        f"Tight Loop ({iterations:,} iterations, 2 instrs/iter)",
        program, expected
    )
    results.append(("Tight Loop", ips, count))
    
    # Test 2: ALU intensive
    iterations = 10000
    program = create_alu_intensive_program(iterations)
    expected = 5 + iterations * 10  # init (5 instrs) + 10 instrs/iteration
    ips, count = await run_benchmark(
        f"ALU Intensive ({iterations:,} iterations, 10 instrs/iter)",
        program, expected
    )
    results.append(("ALU Intensive", ips, count))
    
    # Test 3: Memory intensive
    iterations = 10000
    program = create_memory_intensive_program(iterations)
    expected = 4 + iterations * 6  # init (4 instrs) + 6 instrs/iteration
    ips, count = await run_benchmark(
        f"Memory Intensive ({iterations:,} iterations, 6 instrs/iter)",
        program, expected
    )
    results.append(("Memory Intensive", ips, count))
    
    # Test 4: Fibonacci (realistic mixed workload)
    n = 10000
    program = create_fibonacci_program(n)
    expected = 5 + (n - 1) * 6  # init (5 instrs) + 6 instrs per fib iteration
    ips, count = await run_benchmark(
        f"Fibonacci (n={n:,})",
        program, expected
    )
    results.append(("Fibonacci", ips, count))
    
    # Test 5: Long sustained execution
    iterations = 500000
    program = create_tight_loop_program(iterations)
    expected = 2 + iterations * 2
    ips, count = await run_benchmark(
        f"Sustained Execution ({iterations:,} iterations)",
        program, expected, warmup_runs=1, bench_runs=3
    )
    results.append(("Sustained", ips, count))
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"{'Benchmark':<25} {'Instructions':>15} {'MIPS':>10}")
    print("-" * 50)
    for name, ips, count in results:
        print(f"{name:<25} {int(count):>15,} {ips/1e6:>10.2f}")
    
    avg_ips = sum(r[1] for r in results) / len(results)
    print("-" * 50)
    print(f"{'Average':<25} {'-':>15} {avg_ips/1e6:>10.2f}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
