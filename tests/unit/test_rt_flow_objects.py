"""Unit tests for BufferInstance, StreamInstance, and StatePool."""
import asyncio
import pytest
from zuspec.dataclasses.rt.flow_obj_rt import BufferInstance, StreamInstance, StatePool


def _run(coro):
    return asyncio.run(coro)


# BufferInstance tests

def test_buffer_set_ready_resolves_wait():
    async def _test():
        buf = BufferInstance(obj=42)
        buf.set_ready()
        result = await buf.wait_ready()
        assert result == 42
    _run(_test())


def test_buffer_consumer_gets_correct_object():
    async def _test():
        class MyObj:
            val = 99
        obj = MyObj()
        buf = BufferInstance(obj=obj)
        buf.set_ready()
        result = await buf.wait_ready()
        assert result is obj
    _run(_test())


def test_buffer_double_wait_gets_same_object():
    async def _test():
        buf = BufferInstance(obj="hello")
        buf.set_ready()
        r1 = await buf.wait_ready()
        r2 = await buf.wait_ready()
        assert r1 == r2 == "hello"
    _run(_test())


def test_buffer_wait_before_ready():
    async def _test():
        buf = BufferInstance(obj=7)
        results = []

        async def consumer():
            results.append(await buf.wait_ready())

        async def producer():
            await asyncio.sleep(0)
            buf.set_ready()

        await asyncio.gather(consumer(), producer())
        assert results == [7]
    _run(_test())


# StreamInstance tests

def test_stream_put_get_roundtrip():
    async def _test():
        stream = StreamInstance()
        await stream.put(42)
        result = await stream.get()
        assert result == 42
    _run(_test())


def test_stream_producer_blocks_until_consumed():
    async def _test():
        stream = StreamInstance()
        order = []

        async def producer():
            order.append("put1")
            await stream.put(1)
            order.append("put2")
            await stream.put(2)

        async def consumer():
            await asyncio.sleep(0)
            v1 = await stream.get()
            order.append(f"got{v1}")
            v2 = await stream.get()
            order.append(f"got{v2}")

        await asyncio.gather(producer(), consumer())
        assert "put1" in order
        assert "got1" in order
    _run(_test())


def test_stream_async_producer_consumer():
    async def _test():
        stream = StreamInstance()
        sent = []
        received = []

        async def producer():
            for i in range(3):
                await stream.put(i)
                sent.append(i)

        async def consumer():
            for _ in range(3):
                v = await stream.get()
                received.append(v)

        await asyncio.gather(producer(), consumer())
        assert sent == [0, 1, 2]
        assert received == [0, 1, 2]
    _run(_test())


# StatePool tests

def test_state_initial_flag_true():
    async def _test():
        state = StatePool()
        assert state.initial is True
    _run(_test())


def test_state_initial_flag_false_after_write():
    async def _test():
        state = StatePool()
        await state.write_acquire()
        state.write_release(42)
        assert state.initial is False
    _run(_test())


def test_state_write_exclusive():
    async def _test():
        state = StatePool()
        order = []

        async def writer1():
            await state.write_acquire()
            order.append("w1_start")
            await asyncio.sleep(0)
            order.append("w1_end")
            state.write_release(1)

        async def writer2():
            await asyncio.sleep(0)
            await state.write_acquire()
            order.append("w2_start")
            state.write_release(2)

        await asyncio.gather(writer1(), writer2())
        # w1 must complete before w2 starts
        assert order.index("w1_end") < order.index("w2_start")
    _run(_test())


def test_state_multiple_readers_concurrent():
    async def _test():
        state = StatePool(current=10)
        results = []

        async def reader():
            v = await state.read_acquire()
            results.append(v)
            state.read_release()

        await asyncio.gather(reader(), reader(), reader())
        assert results == [10, 10, 10]
    _run(_test())


def test_state_write_waits_for_all_readers():
    async def _test():
        state = StatePool(current=5)
        order = []

        async def slow_reader():
            v = await state.read_acquire()
            order.append("read_start")
            await asyncio.sleep(0)
            order.append("read_end")
            state.read_release()

        async def writer():
            await asyncio.sleep(0)  # let reader start
            order.append("write_try")
            await state.write_acquire()
            order.append("write_start")
            state.write_release(99)

        await asyncio.gather(slow_reader(), writer())
        # writer must start AFTER reader ends
        assert order.index("read_end") < order.index("write_start")
    _run(_test())


def test_state_value_updated_after_write():
    async def _test():
        state = StatePool(current=0)
        await state.write_acquire()
        state.write_release(42)
        assert state.current == 42
    _run(_test())
