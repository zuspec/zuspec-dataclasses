"""Performance tests for RTL simulation runtime"""
import asyncio
import time
import zuspec.dataclasses as zdc


def benchmark(name, func, iterations=1000):
    """Run a benchmark and return timing results."""
    start = time.perf_counter()
    result = func(iterations)
    end = time.perf_counter()
    elapsed = end - start
    
    return {
        'name': name,
        'iterations': iterations,
        'total_time': elapsed,
        'per_iteration': elapsed / iterations * 1000,  # ms
        'throughput': iterations / elapsed,  # iter/sec
        'result': result
    }


def test_simple_counter_performance():
    """Benchmark: Simple counter with sync process"""
    
    @zdc.dataclass
    class Counter(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        count : zdc.bit32 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _count_proc(self):
            if self.reset:
                self.count = 0
            else:
                self.count = self.count + 1
    
    def run(iterations):
        counter = Counter()
        counter.reset = 0
        
        for i in range(iterations):
            counter.clock = 1
            counter.clock = 0
        
        return counter.count
    
    result = benchmark("Simple Counter (sync process)", run, 10000)
    
    # Verify correctness
    assert result['result'] == 10000
    
    return result


def test_alu_performance():
    """Benchmark: ALU with combinational logic"""
    
    @zdc.dataclass
    class ALU(zdc.Component):
        a : zdc.bit32 = zdc.input()
        b : zdc.bit32 = zdc.input()
        op : zdc.bit8 = zdc.input()
        result : zdc.bit32 = zdc.output()
        
        @zdc.comb
        def _alu_logic(self):
            if self.op == 0:
                self.result = self.a + self.b
            else:
                self.result = self.a - self.b
    
    def run(iterations):
        alu = ALU()
        
        for i in range(iterations):
            alu.a = i % 256
            alu.b = (i * 2) % 256
            alu.op = i % 2
        
        return alu.result
    
    result = benchmark("ALU (comb process)", run, 10000)
    return result


def test_pipelined_design_performance():
    """Benchmark: Pipelined design with sync and comb"""
    
    @zdc.dataclass
    class Pipeline(zdc.Component):
        clock : zdc.bit = zdc.input()
        a : zdc.bit16 = zdc.input()
        b : zdc.bit16 = zdc.input()
        result : zdc.bit16 = zdc.output()
        
        _stage1 : zdc.bit16 = zdc.field()
        _stage2 : zdc.bit16 = zdc.field()
        
        @zdc.comb
        def _add(self):
            self._stage1 = self.a + self.b
        
        @zdc.sync(clock=lambda s: s.clock)
        def _reg1(self):
            self._stage2 = self._stage1
        
        @zdc.sync(clock=lambda s: s.clock)
        def _reg2(self):
            self.result = self._stage2
    
    def run(iterations):
        pipeline = Pipeline()
        
        for i in range(iterations):
            pipeline.a = i % 256
            pipeline.b = (i * 3) % 256
            pipeline.clock = 1
            pipeline.clock = 0
        
        return pipeline.result
    
    result = benchmark("Pipelined Design (sync+comb)", run, 10000)
    return result


def test_cascaded_comb_performance():
    """Benchmark: Cascaded combinational logic (delta cycles)"""
    
    @zdc.dataclass
    class CascadedComb(zdc.Component):
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        out : zdc.bit8 = zdc.output()
        
        _sum : zdc.bit8 = zdc.field()
        _mul : zdc.bit8 = zdc.field()
        
        @zdc.comb
        def _stage1(self):
            self._sum = self.a + self.b
        
        @zdc.comb
        def _stage2(self):
            self._mul = self._sum * 2
        
        @zdc.comb
        def _stage3(self):
            self.out = self._mul + 1
    
    def run(iterations):
        cascaded = CascadedComb()
        
        for i in range(iterations):
            cascaded.a = i % 16
            cascaded.b = (i * 2) % 16
        
        return cascaded.out
    
    result = benchmark("Cascaded Comb (3 stages)", run, 10000)
    return result


def test_wide_datapath_performance():
    """Benchmark: Wide datapath operations"""
    
    @zdc.dataclass
    class WideDatapath(zdc.Component):
        clock : zdc.bit = zdc.input()
        a : zdc.bit32 = zdc.input()
        b : zdc.bit32 = zdc.input()
        c : zdc.bit32 = zdc.input()
        d : zdc.bit32 = zdc.input()
        result : zdc.bit32 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock)
        def _compute(self):
            self.result = (self.a + self.b) * (self.c - self.d)
    
    def run(iterations):
        datapath = WideDatapath()
        
        for i in range(iterations):
            datapath.a = i % 1000
            datapath.b = (i * 2) % 1000
            datapath.c = (i * 3) % 1000
            datapath.d = (i * 4) % 1000
            datapath.clock = 1
            datapath.clock = 0
        
        return datapath.result
    
    result = benchmark("Wide Datapath (32-bit)", run, 10000)
    return result


def test_complex_control_flow_performance():
    """Benchmark: Complex control flow with nested if/else"""
    
    @zdc.dataclass
    class StateMachine(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        input_val : zdc.bit8 = zdc.input()
        state : zdc.bit8 = zdc.output()
        output_val : zdc.bit8 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _state_machine(self):
            if self.reset:
                self.state = 0
                self.output_val = 0
            else:
                if self.state == 0:
                    self.output_val = self.input_val
                    self.state = 1
                else:
                    if self.state == 1:
                        self.output_val = self.input_val * 2
                        self.state = 2
                    else:
                        if self.state == 2:
                            self.output_val = self.input_val + 10
                            self.state = 0
                        else:
                            self.state = 0
    
    def run(iterations):
        sm = StateMachine()
        sm.reset = 1
        sm.clock = 1
        sm.clock = 0
        sm.reset = 0
        
        for i in range(iterations):
            sm.input_val = i % 64
            sm.clock = 1
            sm.clock = 0
        
        return sm.state
    
    result = benchmark("State Machine (complex control)", run, 10000)
    return result


def test_initialization_overhead():
    """Benchmark: Component initialization overhead"""
    
    @zdc.dataclass
    class SimpleComponent(zdc.Component):
        clock : zdc.bit = zdc.input()
        data : zdc.bit32 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock)
        def _proc(self):
            self.data = self.data + 1
    
    def run(iterations):
        comps = []
        for i in range(iterations):
            comp = SimpleComponent()
            comps.append(comp)
        return len(comps)
    
    result = benchmark("Initialization Overhead", run, 1000)
    return result


def run_all_benchmarks():
    """Run all performance benchmarks and display results."""
    print("\n" + "="*80)
    print("RTL SIMULATION PERFORMANCE BENCHMARKS")
    print("="*80)
    print()
    
    benchmarks = [
        test_simple_counter_performance,
        test_alu_performance,
        test_pipelined_design_performance,
        test_cascaded_comb_performance,
        test_wide_datapath_performance,
        test_complex_control_flow_performance,
        test_initialization_overhead,
    ]
    
    results = []
    for bench_func in benchmarks:
        print(f"Running: {bench_func.__doc__.split(':')[1].strip()}...", end=" ", flush=True)
        result = bench_func()
        results.append(result)
        print(f"✓ {result['throughput']:.0f} iter/sec")
    
    print("\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)
    print()
    
    # Table header
    print(f"{'Benchmark':<40} {'Iterations':>12} {'Total(s)':>10} {'Per-Iter(ms)':>12} {'Throughput':>15}")
    print("-" * 90)
    
    for r in results:
        print(f"{r['name']:<40} {r['iterations']:>12} {r['total_time']:>10.3f} "
              f"{r['per_iteration']:>12.4f} {r['throughput']:>12.0f} /sec")
    
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print()
    
    # Calculate summary stats
    throughputs = [r['throughput'] for r in results if 'Initialization' not in r['name']]
    avg_throughput = sum(throughputs) / len(throughputs)
    max_throughput = max(throughputs)
    min_throughput = min(throughputs)
    
    print(f"Average Throughput:  {avg_throughput:>12.0f} iterations/sec")
    print(f"Maximum Throughput:  {max_throughput:>12.0f} iterations/sec")
    print(f"Minimum Throughput:  {min_throughput:>12.0f} iterations/sec")
    print()
    
    # Cycles per second estimation (assuming 1 clock per iteration for sync designs)
    avg_cycles_per_sec = avg_throughput
    print(f"Estimated Avg:       {avg_cycles_per_sec:>12.0f} clock cycles/sec")
    print()
    
    # Performance characteristics
    print("PERFORMANCE CHARACTERISTICS:")
    print()
    print(f"  • Comb process overhead:     ~{1000/results[1]['throughput']:.3f} ms per evaluation")
    print(f"  • Sync process overhead:     ~{1000/results[0]['throughput']:.3f} ms per clock edge")
    print(f"  • Delta cycle overhead:      ~{1000/results[3]['throughput']:.3f} ms per cascade")
    print(f"  • Initialization overhead:   ~{results[6]['per_iteration']:.3f} ms per component")
    print()
    
    print("="*80)
    print()
    
    return results


if __name__ == "__main__":
    results = run_all_benchmarks()
