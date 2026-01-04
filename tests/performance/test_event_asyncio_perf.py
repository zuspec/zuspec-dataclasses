"""Performance test for Component.wait() with standard asyncio."""

import asyncio
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
import zuspec.dataclasses as zdc


@pytest.mark.asyncio
async def test_component_wait_many_tasks_asyncio():
    """Benchmark many concurrent tasks with simulated time delays."""
    num_tasks = 1000
    sim_delay_ns = 100
    
    @zdc.dataclass
    class TestBench(zdc.Component):
        pass
    
    bench = TestBench()
    completion_count = [0]
    
    async def task_with_wait(task_id):
        await bench.wait(zdc.Time.ns(sim_delay_ns))
        completion_count[0] += 1
    
    # Create all tasks
    start_time = time.perf_counter()
    
    tasks = [asyncio.create_task(task_with_wait(i)) for i in range(num_tasks)]
    
    # Advance simulation time to complete all tasks
    await bench.wait(zdc.Time.ns(sim_delay_ns + 10))
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks)
    
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    
    assert completion_count[0] == num_tasks
    
    return {
        'name': 'Many Tasks with Component.wait() (asyncio)',
        'num_tasks': num_tasks,
        'sim_delay_ns': sim_delay_ns,
        'total_time': elapsed,
        'tasks_per_sec': num_tasks / elapsed,
    }


@pytest.mark.asyncio
async def test_component_wait_varied_delays_asyncio():
    """Benchmark tasks with varied simulation delays."""
    num_tasks = 500
    
    @zdc.dataclass
    class TestBench(zdc.Component):
        pass
    
    bench = TestBench()
    completion_count = [0]
    
    async def task_with_varied_wait(task_id):
        # Different delays: 10ns, 50ns, 100ns, 200ns
        delay = 10 * (1 << (task_id % 4))
        await bench.wait(zdc.Time.ns(delay))
        completion_count[0] += 1
    
    start_time = time.perf_counter()
    
    tasks = [asyncio.create_task(task_with_varied_wait(i)) for i in range(num_tasks)]
    
    # Advance simulation time to complete all tasks (200ns + margin)
    await bench.wait(zdc.Time.ns(250))
    
    await asyncio.gather(*tasks)
    
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    
    assert completion_count[0] == num_tasks
    
    return {
        'name': 'Varied Delays (asyncio)',
        'num_tasks': num_tasks,
        'total_time': elapsed,
        'tasks_per_sec': num_tasks / elapsed,
    }


@pytest.mark.asyncio
async def test_component_wait_sequential_waves_asyncio():
    """Benchmark sequential waves of concurrent tasks."""
    num_waves = 10
    tasks_per_wave = 200
    wave_delay_ns = 50
    
    @zdc.dataclass
    class TestBench(zdc.Component):
        pass
    
    bench = TestBench()
    completion_count = [0]
    
    async def task_in_wave(wave_id):
        await bench.wait(zdc.Time.ns((wave_id + 1) * wave_delay_ns))
        completion_count[0] += 1
    
    start_time = time.perf_counter()
    
    all_tasks = []
    for wave in range(num_waves):
        for _ in range(tasks_per_wave):
            task = asyncio.create_task(task_in_wave(wave))
            all_tasks.append(task)
    
    # Advance simulation time to complete all waves
    await bench.wait(zdc.Time.ns((num_waves + 1) * wave_delay_ns))
    
    await asyncio.gather(*all_tasks)
    
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    
    total_tasks = num_waves * tasks_per_wave
    assert completion_count[0] == total_tasks
    
    return {
        'name': 'Sequential Waves (asyncio)',
        'num_waves': num_waves,
        'tasks_per_wave': tasks_per_wave,
        'total_tasks': total_tasks,
        'total_time': elapsed,
        'tasks_per_sec': total_tasks / elapsed,
    }


async def run_all_benchmarks():
    """Run all performance benchmarks."""
    print("\n" + "="*80)
    print("Component.wait() PERFORMANCE BENCHMARKS - Standard asyncio")
    print("="*80)
    print()
    
    benchmarks = [
        test_component_wait_many_tasks_asyncio,
        test_component_wait_varied_delays_asyncio,
        test_component_wait_sequential_waves_asyncio,
    ]
    
    results = []
    for bench_func in benchmarks:
        print(f"Running: {bench_func.__doc__.strip()}...", flush=True)
        result = await bench_func()
        results.append(result)
        print(f"  ✓ Completed in {result['total_time']:.3f}s")
    
    print("\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)
    print()
    
    for r in results:
        print(f"\n{r['name']}:")
        print(f"  Total Time:      {r['total_time']:.4f}s")
        if 'num_tasks' in r:
            print(f"  Num Tasks:       {r['num_tasks']}")
        if 'sim_delay_ns' in r:
            print(f"  Sim Delay:       {r['sim_delay_ns']}ns")
        if 'tasks_per_sec' in r:
            print(f"  Tasks/sec:       {r['tasks_per_sec']:.2f}")
    
    print("\n" + "="*80)
    print()
    
    return results


if __name__ == "__main__":
    results = asyncio.run(run_all_benchmarks())
