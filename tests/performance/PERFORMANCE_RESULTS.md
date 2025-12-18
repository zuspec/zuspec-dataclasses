# RTL Simulation Performance Results

**Date:** December 17, 2024  
**Platform:** Python 3.12.3 on Linux  
**Implementation:** zuspec-dataclasses RTL simulation runtime

---

## Executive Summary

The Python-based RTL simulation runtime achieves **~283,000 clock cycles per second** on average across various benchmark scenarios. Peak throughput reaches **925,000 iterations/sec** for pure combinational logic.

### Key Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Average Throughput** | 282,727 cycles/sec | Across all sync/comb benchmarks |
| **Peak Throughput** | 925,589 iter/sec | Pure combinational logic (ALU) |
| **Clock Edge Overhead** | 0.005 ms | Sync process execution |
| **Comb Evaluation Overhead** | 0.001 ms | Single comb process |
| **Initialization Cost** | 7.4 ms | Per component creation |

---

## Detailed Benchmark Results

### 1. Simple Counter (Sync Process)
- **Throughput:** 184,557 cycles/sec
- **Per-iteration:** 0.0054 ms
- **Description:** Basic counter with reset and increment logic
- **Analysis:** Representative of simple sequential logic performance

### 2. ALU (Combinational Logic) ⭐ FASTEST
- **Throughput:** 925,589 iter/sec
- **Per-iteration:** 0.0011 ms
- **Description:** Arithmetic logic unit with add/subtract operations
- **Analysis:** Pure combinational logic is ~5x faster than sequential logic due to no clock edge processing

### 3. Pipelined Design (Sync + Comb) 🐌 SLOWEST
- **Throughput:** 84,796 cycles/sec
- **Per-iteration:** 0.0118 ms
- **Description:** Two-stage pipeline with combinational and sequential stages
- **Analysis:** Multiple sync processes per clock create overhead; realistic design pattern

### 4. Cascaded Combinational Logic (Delta Cycles)
- **Throughput:** 180,395 iter/sec
- **Per-iteration:** 0.0055 ms
- **Description:** 3-stage combinational cascade triggering watchers
- **Analysis:** Delta-cycle overhead is minimal; watcher system performs well

### 5. Wide Datapath (32-bit Operations)
- **Throughput:** 135,460 cycles/sec
- **Per-iteration:** 0.0074 ms
- **Description:** Complex arithmetic with multiple 32-bit operands
- **Analysis:** Wider datapaths have moderate overhead from complex expression evaluation

### 6. State Machine (Complex Control Flow)
- **Throughput:** 185,566 cycles/sec
- **Per-iteration:** 0.0054 ms
- **Description:** Multi-state FSM with nested if/else logic
- **Analysis:** Control-heavy designs perform similarly to simple counters

### 7. Initialization Overhead
- **Throughput:** 135 components/sec
- **Per-component:** 7.41 ms
- **Description:** Component creation and datamodel build time
- **Analysis:** One-time cost; negligible for long-running simulations

---

## Performance Characteristics

### Overhead Breakdown

```
Component Creation:      7.410 ms  (one-time cost)
Sync Process (clock):    0.005 ms  (per clock edge)
Comb Process:            0.001 ms  (per evaluation)  
Delta Cycle:             0.006 ms  (per cascade stage)
```

### Scaling Characteristics

- **Pure Comb Logic:** ~1 μs per evaluation ✅ Excellent
- **Sequential Logic:** ~5 μs per clock edge ✅ Good
- **Pipelined Logic:** ~12 μs per clock edge ⚠️ Fair (multiple processes)
- **Initialization:** ~7.4 ms per component ⚠️ Amortized over simulation

---

## Performance Comparison

### Relative Performance (normalized to simple counter)

| Design Pattern | Relative Speed |
|----------------|----------------|
| ALU (pure comb) | 5.0x faster |
| State Machine | 1.0x (baseline) |
| Simple Counter | 1.0x (baseline) |
| Cascaded Comb | 0.98x |
| Wide Datapath | 0.73x |
| Pipeline | 0.46x |

---

## Bottleneck Analysis

### Major Cost Centers

1. **Clock Edge Processing (sync)** - 5 μs overhead
   - Process scheduling
   - Deferred write commit
   - Watcher notification

2. **Component Initialization** - 7.4 ms one-time
   - Datamodel factory AST parsing
   - Sensitivity list computation
   - Watcher registration

3. **Multiple Sync Processes** - Linear overhead
   - Each sync process adds ~5 μs per clock
   - Pipeline with 2 sync processes: ~12 μs total

### Minor Cost Centers

1. **Combinational Logic** - 1 μs per eval
   - Watcher callbacks very efficient
   - Delta cycles work well

2. **Expression Evaluation** - Sub-microsecond
   - Python arithmetic is fast
   - AST interpretation overhead minimal

---

## Use Case Recommendations

### ✅ **Ideal For:**
- Functional verification of RTL designs (up to ~10K cycles)
- Algorithm prototyping and golden model development
- Educational purposes and RTL learning
- Co-simulation with software models
- Debugging specific corner cases

### ⚠️ **Consider Alternatives For:**
- Long-running simulations (>1M cycles)
  - Use: Verilator, commercial simulators
- High-performance gate-level simulation
  - Use: Event-driven simulators
- Production regression testing at scale
  - Use: Cloud-based simulation farms

### 🎯 **Sweet Spot:**
- **10-100K cycle simulations** for design exploration
- **Block-level verification** of RTL modules
- **Python-integrated workflows** leveraging dataclasses ecosystem

---

## Optimization Opportunities

### Short-term (Low-hanging fruit)
1. **Cache datamodel construction** - Eliminate 7.4ms initialization
2. **Batch clock edges** - Reduce per-cycle overhead
3. **Optimize field lookup** - Use direct indexing vs dict

### Medium-term
1. **JIT compilation** - Compile hot paths with Numba/PyPy
2. **Parallel evaluation** - Multi-thread independent comb processes
3. **Incremental sensitivity** - Only re-evaluate changed signals

### Long-term
1. **C++ runtime** - Port hot paths to native code via pybind11
2. **Cycle-accurate backend** - Compile to event-driven engine
3. **Hardware acceleration** - FPGA-based simulation backend

---

## Conclusions

### Strengths ✅
- **Pure Python implementation** - Easy to debug and extend
- **Competitive performance** for small/medium designs
- **Correct RTL semantics** - Deferred/immediate assignment works properly
- **Delta-cycle support** - Cascaded comb logic handled correctly
- **Excellent for prototyping** - 280K cycles/sec is sufficient for many use cases

### Limitations ⚠️
- **Initialization overhead** - 7.4ms per component (acceptable for long sims)
- **Sequential logic cost** - 5 μs per clock edge (limits to ~200K Hz)
- **Pipeline overhead** - Multiple sync processes scale linearly

### Recommendation 🎯
**The Python runtime is production-ready for:**
- Design exploration and algorithm development
- Block-level RTL verification (up to 100K cycles)
- Python-native workflows requiring tight integration
- Educational and prototyping purposes

**For production-scale regression testing**, consider augmenting with:
- VCD export + replay in faster simulator
- Selective C++ compilation of hot paths
- Integration with Verilator for long-running tests

---

## Appendix: Raw Data

```
Benchmark                                  Iterations   Total(s) Per-Iter(ms)      Throughput
------------------------------------------------------------------------------------------
Simple Counter (sync process)                   10000      0.054       0.0054       184557 /sec
ALU (comb process)                              10000      0.011       0.0011       925589 /sec
Pipelined Design (sync+comb)                    10000      0.118       0.0118        84796 /sec
Cascaded Comb (3 stages)                        10000      0.055       0.0055       180395 /sec
Wide Datapath (32-bit)                          10000      0.074       0.0074       135460 /sec
State Machine (complex control)                 10000      0.054       0.0054       185566 /sec
Initialization Overhead                          1000      7.410       7.4100          135 /sec
```

**Test Environment:**
- CPU: (Linux system)
- Python: 3.12.3
- Libraries: dataclasses (stdlib), no external dependencies
- Optimization: CPython default (no JIT)
