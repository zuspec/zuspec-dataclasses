"""Tests for PSS flow-object and resource base types, and lock/share helpers."""
import dataclasses
import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Flow-object base type class hierarchy
# ---------------------------------------------------------------------------

def test_buffer_subclass_hierarchy():
    """Buffer subclass correctly inherits from Buffer and Struct."""
    @zdc.dataclass
    class MyBuf(zdc.Buffer):
        seg_base: zdc.u32 = zdc.rand()

    assert issubclass(MyBuf, zdc.Buffer)
    assert issubclass(MyBuf, zdc.Struct)


def test_stream_subclass_hierarchy():
    """Stream subclass correctly inherits from Stream and Struct."""
    @zdc.dataclass
    class MyStream(zdc.Stream):
        data: zdc.u8 = zdc.rand()

    assert issubclass(MyStream, zdc.Stream)
    assert issubclass(MyStream, zdc.Struct)


def test_state_subclass_hierarchy():
    """State subclass correctly inherits from State and Struct."""
    @zdc.dataclass
    class MyState(zdc.State):
        value: zdc.u32 = zdc.rand()

    assert issubclass(MyState, zdc.State)
    assert issubclass(MyState, zdc.Struct)


def test_state_has_initial_field():
    """State base class has 'initial' attribute defaulting to False."""
    assert hasattr(zdc.State, 'initial')
    assert zdc.State.initial is False


def test_resource_subclass_hierarchy():
    """Resource subclass correctly inherits from Resource and Struct."""
    @zdc.dataclass
    class MyResource(zdc.Resource):
        priority: zdc.u4 = zdc.rand()

    assert issubclass(MyResource, zdc.Resource)
    assert issubclass(MyResource, zdc.Struct)


def test_resource_has_instance_id():
    """Resource base class has 'instance_id' attribute defaulting to 0."""
    assert hasattr(zdc.Resource, 'instance_id')
    assert zdc.Resource.instance_id == 0


# ---------------------------------------------------------------------------
# lock() / share() field helpers
# ---------------------------------------------------------------------------

def test_lock_metadata():
    """lock() produces a field with resource_ref/lock metadata."""
    @zdc.dataclass
    class DmaChannel(zdc.Resource):
        priority: zdc.u4 = zdc.rand()

    @zdc.dataclass
    class MyAction(zdc.Action[zdc.Component]):
        chan: DmaChannel = zdc.lock()

    fields = {f.name: f for f in dataclasses.fields(MyAction)}
    meta = fields['chan'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'lock'


def test_share_metadata():
    """share() produces a field with resource_ref/share metadata."""
    @zdc.dataclass
    class CpuCore(zdc.Resource):
        pass

    @zdc.dataclass
    class MyAction(zdc.Action[zdc.Component]):
        cpu: CpuCore = zdc.share()

    fields = {f.name: f for f in dataclasses.fields(MyAction)}
    meta = fields['cpu'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'share'


def test_lock_with_size_metadata():
    """lock(size=N) includes size in metadata."""
    @zdc.dataclass
    class Chan(zdc.Resource):
        pass

    @zdc.dataclass
    class MyAction(zdc.Action[zdc.Component]):
        chans: list = zdc.lock(size=4)

    fields = {f.name: f for f in dataclasses.fields(MyAction)}
    meta = fields['chans'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'lock'
    assert meta['size'] == 4


def test_share_with_size_metadata():
    """share(size=N) includes size in metadata."""
    @zdc.dataclass
    class Core(zdc.Resource):
        pass

    @zdc.dataclass
    class MyAction(zdc.Action[zdc.Component]):
        cores: list = zdc.share(size=2)

    fields = {f.name: f for f in dataclasses.fields(MyAction)}
    meta = fields['cores'].metadata
    assert meta['size'] == 2
    assert meta['claim'] == 'share'
