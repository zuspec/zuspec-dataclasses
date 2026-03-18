"""Tests for the pool() decorator (Phase 2 additions)."""
import dataclasses as dc
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool


def test_pool_returns_field_descriptor():
    """pool() returns a dc.Field, not None."""
    f = zdc.pool()
    assert isinstance(f, dc.Field)


def test_pool_metadata_kind():
    """pool() field has metadata kind='pool'."""
    f = zdc.pool()
    assert f.metadata.get("kind") == "pool"


def test_pool_with_size_metadata():
    """pool(size=N) stores size in metadata."""
    f = zdc.pool(size=4)
    assert f.metadata.get("size") == 4


def test_pool_default_is_none():
    """pool() default is None when no factory given."""
    f = zdc.pool()
    assert f.default is None


def test_pool_with_default_factory():
    """pool(default_factory=...) uses the factory."""
    @zdc.dataclass
    class MyResource(zdc.Resource):
        pass

    factory = lambda: ClaimPool.fromList([MyResource(), MyResource()])
    f = zdc.pool(default_factory=factory)
    assert f.default_factory is factory


def test_pool_on_component_field():
    """pool() can be declared on a Component field."""
    from zuspec.dataclasses.rt.resource_rt import make_resource

    @zdc.dataclass
    class Chan(zdc.Resource):
        pass

    @zdc.dataclass
    class MyComp(zdc.Component):
        channels: ClaimPool = zdc.pool(
            default_factory=lambda: ClaimPool.fromList([
                make_resource(Chan), make_resource(Chan)
            ])
        )

    comp = MyComp()
    fields = {f.name: f for f in dc.fields(MyComp)}
    assert "channels" in fields
    assert fields["channels"].metadata.get("kind") == "pool"
