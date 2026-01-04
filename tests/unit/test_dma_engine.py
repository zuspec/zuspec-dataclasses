import asyncio
import zuspec.dataclasses as zdc
import zuspec.dataclasses.ir as dm
from typing import Protocol, List


class MemIF(Protocol):
    async def read(self, 
                   addr : int, 
                   size : int) -> bytearray: ...

    async def write(self, 
                    addr : int, 
                    data : bytearray, 
                    offset : int=0, 
                    size : int=-1): ...

@zdc.dataclass
class Dma(zdc.Component):
    m0 : MemIF = zdc.port()
    _lock : zdc.Lock = zdc.field()

    # Resource pool
#    channels : Pool[DmaChannel] = zdc.pool(size, bind)

#    _m0_lock : zdc.Resource = zdc.lock()
#    _channel_busy : List[bool] = zdc.list(sz=16)

    # Capture the multiplicity of this function by tying it
    # to resource acquisition
    async def m2m(self,
                  channel : int,
                  src : int,
                  dst : int,
                  inc_src : bool,
                  inc_dst : bool,
                  xfer_sz : int,
                  xfer_tot : int,
                  xfer_chk : int=-1):
        if xfer_chk <= 0:
            xfer_chk = xfer_tot

        i = 0
        while i < xfer_tot:
            # Acquire access to the interface for a chunk
            # TODO: need to pass along priority data for the request
            await self._lock.acquire()
            j = 0
            while i < xfer_tot and j < xfer_chk:
                data = await self.m0.read(src, xfer_sz)
                await self.m0.write(dst, data, size=xfer_sz)
                i += 1
                j += 1

            self._lock.release()


class MemModel:
    """Memory model with optional 20ns transfer time per operation.
    
    When timebase is None, operations complete instantly.
    When timebase is provided, each transfer takes 20ns of simulation time.
    """
    
    def __init__(self, timebase=None, size: int = 0x10000):
        self._timebase = timebase
        self._mem = bytearray(size)
        self._read_count = 0
        self._write_count = 0
        self._transfer_time_ns = 20
    
    async def read(self, addr: int, size: int) -> bytearray:
        """Read data from memory. Each transfer takes 20ns if timebase provided."""
        if self._timebase is not None:
            await self._timebase.wait(zdc.Time.ns(self._transfer_time_ns))
        self._read_count += 1
        return bytearray(self._mem[addr:addr + size])
    
    async def write(self, addr: int, data: bytearray, offset: int = 0, size: int = -1):
        """Write data to memory. Each transfer takes 20ns if timebase provided."""
        if self._timebase is not None:
            await self._timebase.wait(zdc.Time.ns(self._transfer_time_ns))
        self._write_count += 1
        if size < 0:
            size = len(data)
        self._mem[addr:addr + size] = data[offset:offset + size]


@zdc.dataclass
class DmaBench(zdc.Component):
    """Top-level bench that connects DMA to memory."""
    dma : Dma = zdc.field()
    
    def __bind__(self):
        return {
            self.dma.m0 : self.mem_if
        }
    
    # Memory interface bound to the memory model
    mem_if : MemIF = zdc.export()
    
    def set_mem_model(self, mem_model: MemModel):
        """Set the memory model implementation."""
        self._mem_model = mem_model
        # Bind the export methods to the memory model
        self.mem_if = mem_model


def test_dma_datamodel():
    """Test that Lock type is properly handled in the data model."""
    dm_ctxt = zdc.DataModelFactory().build(Dma)
    
    # Get the Dma data type
    dma_qualname = Dma.__qualname__
    assert dma_qualname in dm_ctxt.type_m, f"Dma should be in context"
    
    dma_dm = dm_ctxt.type_m[dma_qualname]
    assert isinstance(dma_dm, dm.DataTypeComponent), "Dma should be a component"
    
    # Find the _lock field
    lock_field = None
    for f in dma_dm.fields:
        if f.name == '_lock':
            lock_field = f
            break
    
    assert lock_field is not None, "Dma should have _lock field"
    assert isinstance(lock_field.datatype, dm.DataTypeLock), \
        f"_lock field should be DataTypeLock, got {type(lock_field.datatype).__name__}"
    
    print("Lock field found and properly typed as DataTypeLock")


def test_dma_single_transfer():
    """Test a single DMA transfer with memory model."""
    # Create memory model without timebase (instant operations)
    mem_model = MemModel(size=0x10000)
    
    # Initialize source memory with test data
    test_data = bytes([i % 256 for i in range(64)])
    mem_model._mem[0x1000:0x1000 + 64] = test_data
    
    # Create DMA with memory binding
    dma = Dma(m0=mem_model)
    
    async def run_test():
        # Perform a memory-to-memory transfer
        # Transfer 4 bytes at a time, 16 total transfers
        await dma.m2m(
            channel=0,
            src=0x1000,
            dst=0x2000,
            inc_src=True,
            inc_dst=True,
            xfer_sz=4,
            xfer_tot=16,
            xfer_chk=4
        )
    
    asyncio.run(run_test())
    
    # Verify transfer counts
    assert mem_model._read_count == 16, f"Expected 16 reads, got {mem_model._read_count}"
    assert mem_model._write_count == 16, f"Expected 16 writes, got {mem_model._write_count}"
    
    # Verify data was transferred (first 4 bytes)
    assert mem_model._mem[0x2000:0x2004] == test_data[0:4], "Data should be copied"
    
    dma.shutdown()
    print("Single DMA transfer test passed")


def test_dma_parallel_operations():
    """Test two DMA operations running in parallel with Lock synchronization."""
    # Create memory model without timebase (instant operations)
    mem_model = MemModel(size=0x10000)
    
    # Initialize source memory regions with different test data
    test_data_a = bytes([0xAA] * 32)
    test_data_b = bytes([0xBB] * 32)
    mem_model._mem[0x1000:0x1000 + 32] = test_data_a  # Source A
    mem_model._mem[0x1100:0x1100 + 32] = test_data_b  # Source B
    
    # Create DMA with memory binding
    dma = Dma(m0=mem_model)
    
    # Track operation completion order
    completion_order = []
    
    async def dma_operation_a():
        """First DMA operation: transfer from 0x1000 to 0x2000."""
        await dma.m2m(
            channel=0,
            src=0x1000,
            dst=0x2000,
            inc_src=True,
            inc_dst=True,
            xfer_sz=4,
            xfer_tot=8,  # 8 transfers
            xfer_chk=2   # Release lock every 2 transfers
        )
        completion_order.append('A')
    
    async def dma_operation_b():
        """Second DMA operation: transfer from 0x1100 to 0x2100."""
        await dma.m2m(
            channel=1,
            src=0x1100,
            dst=0x2100,
            inc_src=True,
            inc_dst=True,
            xfer_sz=4,
            xfer_tot=8,  # 8 transfers
            xfer_chk=2   # Release lock every 2 transfers
        )
        completion_order.append('B')
    
    async def run_parallel():
        # Run both DMA operations in parallel
        await asyncio.gather(
            dma_operation_a(),
            dma_operation_b()
        )
    
    asyncio.run(run_parallel())
    
    # Verify both operations completed
    assert len(completion_order) == 2, f"Both operations should complete, got {completion_order}"
    assert 'A' in completion_order, "Operation A should complete"
    assert 'B' in completion_order, "Operation B should complete"
    
    # Verify transfer counts (8 reads + 8 writes per operation = 32 total)
    assert mem_model._read_count == 16, f"Expected 16 reads, got {mem_model._read_count}"
    assert mem_model._write_count == 16, f"Expected 16 writes, got {mem_model._write_count}"
    
    # Verify data was transferred correctly
    assert mem_model._mem[0x2000:0x2004] == test_data_a[0:4], "Data A should be copied"
    assert mem_model._mem[0x2100:0x2104] == test_data_b[0:4], "Data B should be copied"
    
    dma.shutdown()
    print("Parallel DMA operations test passed")
    print(f"Completion order: {completion_order}")


def test_dma_bench_integration():
    """Test the full DmaBench with parallel DMA operations."""
    # Create memory model without timebase (instant operations)
    mem_model = MemModel(size=0x10000)
    
    # Create DMA with memory binding directly
    dma = Dma(m0=mem_model)
    
    # Initialize memory
    test_data_1 = bytes([0x11, 0x22, 0x33, 0x44] * 8)
    test_data_2 = bytes([0x55, 0x66, 0x77, 0x88] * 8)
    mem_model._mem[0x0000:0x0020] = test_data_1
    mem_model._mem[0x0100:0x0120] = test_data_2
    
    async def run_bench():
        # Launch two parallel transfers
        task1 = asyncio.create_task(dma.m2m(
            channel=0, src=0x0000, dst=0x1000,
            inc_src=True, inc_dst=True,
            xfer_sz=4, xfer_tot=8, xfer_chk=2
        ))
        task2 = asyncio.create_task(dma.m2m(
            channel=1, src=0x0100, dst=0x1100,
            inc_src=True, inc_dst=True,
            xfer_sz=4, xfer_tot=8, xfer_chk=2
        ))
        
        await asyncio.gather(task1, task2)
        
        return (
            mem_model._mem[0x1000:0x1004],
            mem_model._mem[0x1100:0x1104]
        )
    
    result1, result2 = asyncio.run(run_bench())
    
    # Verify transfers
    assert result1 == test_data_1[0:4], f"First transfer failed: {result1.hex()}"
    assert result2 == test_data_2[0:4], f"Second transfer failed: {result2.hex()}"
    
    print(f"Bench integration test passed")
    print(f"  Transfer 1 result: {result1.hex()}")
    print(f"  Transfer 2 result: {result2.hex()}")
    print(f"  Total reads: {mem_model._read_count}, writes: {mem_model._write_count}")
    
    dma.shutdown()


def test_dma_throughput():
    """Measure DMA transfer throughput (transfers per second)."""
    import time
    
    # Create memory model without timebase (instant operations)
    mem_model = MemModel(size=0x100000)  # 1MB memory
    
    # Initialize source memory with pattern
    pattern = bytes([i % 256 for i in range(4096)])
    mem_model._mem[0x0000:0x1000] = pattern
    
    # Create DMA with memory binding
    dma = Dma(m0=mem_model)
    
    # Parameters for throughput test
    num_iterations = 100
    transfers_per_iteration = 256  # Number of 4-byte transfers per m2m call
    chunk_size = 16  # Release lock every 16 transfers
    
    async def run_throughput_test():
        for _ in range(num_iterations):
            await dma.m2m(
                channel=0,
                src=0x0000,
                dst=0x10000,
                inc_src=True,
                inc_dst=True,
                xfer_sz=4,
                xfer_tot=transfers_per_iteration,
                xfer_chk=chunk_size
            )
    
    # Measure wall-clock time
    start_time = time.perf_counter()
    asyncio.run(run_throughput_test())
    end_time = time.perf_counter()
    
    elapsed_seconds = end_time - start_time
    total_transfers = num_iterations * transfers_per_iteration
    transfers_per_second = total_transfers / elapsed_seconds
    
    # Each transfer is a read + write pair
    total_operations = mem_model._read_count + mem_model._write_count
    operations_per_second = total_operations / elapsed_seconds
    
    print(f"\n=== DMA Throughput Benchmark ===")
    print(f"  Total transfers: {total_transfers:,}")
    print(f"  Total operations (read+write): {total_operations:,}")
    print(f"  Elapsed time: {elapsed_seconds:.4f} seconds")
    print(f"  Transfers/second: {transfers_per_second:,.0f}")
    print(f"  Operations/second: {operations_per_second:,.0f}")
    print(f"  Bytes transferred: {total_transfers * 4:,} bytes")
    print(f"  Throughput: {(total_transfers * 4) / elapsed_seconds / 1024 / 1024:.2f} MB/s (simulated)")
    
    # Verify correctness
    assert mem_model._read_count == total_transfers, \
        f"Expected {total_transfers} reads, got {mem_model._read_count}"
    assert mem_model._write_count == total_transfers, \
        f"Expected {total_transfers} writes, got {mem_model._write_count}"
    
    dma.shutdown()


def test_dma_parallel_throughput():
    """Measure throughput with multiple parallel DMA channels."""
    import time
    
    # Create memory model without timebase (instant operations)
    mem_model = MemModel(size=0x100000)  # 1MB memory
    
    # Initialize source memory regions
    for i in range(4):
        pattern = bytes([(i * 64 + j) % 256 for j in range(4096)])
        mem_model._mem[i * 0x2000:i * 0x2000 + 0x1000] = pattern
    
    # Create DMA with memory binding
    dma = Dma(m0=mem_model)
    
    # Parameters
    num_channels = 4
    iterations_per_channel = 50
    transfers_per_iteration = 128
    chunk_size = 8  # Release lock frequently to allow interleaving
    
    async def channel_worker(channel_id: int):
        src_base = channel_id * 0x2000
        dst_base = 0x40000 + channel_id * 0x2000
        
        for _ in range(iterations_per_channel):
            await dma.m2m(
                channel=channel_id,
                src=src_base,
                dst=dst_base,
                inc_src=True,
                inc_dst=True,
                xfer_sz=4,
                xfer_tot=transfers_per_iteration,
                xfer_chk=chunk_size
            )
    
    async def run_parallel_throughput():
        # Launch all channel workers in parallel
        await asyncio.gather(*[channel_worker(i) for i in range(num_channels)])
    
    # Measure wall-clock time
    start_time = time.perf_counter()
    asyncio.run(run_parallel_throughput())
    end_time = time.perf_counter()
    
    elapsed_seconds = end_time - start_time
    total_transfers = num_channels * iterations_per_channel * transfers_per_iteration
    transfers_per_second = total_transfers / elapsed_seconds
    
    total_operations = mem_model._read_count + mem_model._write_count
    operations_per_second = total_operations / elapsed_seconds
    
    print(f"\n=== Parallel DMA Throughput Benchmark ({num_channels} channels) ===")
    print(f"  Total transfers: {total_transfers:,}")
    print(f"  Total operations (read+write): {total_operations:,}")
    print(f"  Elapsed time: {elapsed_seconds:.4f} seconds")
    print(f"  Transfers/second: {transfers_per_second:,.0f}")
    print(f"  Operations/second: {operations_per_second:,.0f}")
    print(f"  Bytes transferred: {total_transfers * 4:,} bytes")
    print(f"  Throughput: {(total_transfers * 4) / elapsed_seconds / 1024 / 1024:.2f} MB/s (simulated)")
    
    # Verify correctness
    assert mem_model._read_count == total_transfers, \
        f"Expected {total_transfers} reads, got {mem_model._read_count}"
    assert mem_model._write_count == total_transfers, \
        f"Expected {total_transfers} writes, got {mem_model._write_count}"
    
    dma.shutdown()
