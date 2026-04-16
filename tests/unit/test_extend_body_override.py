"""Tests for @zdc.extend body() override semantics (Item 3 — ECO Foundation).

Verifies:
- @zdc.extend sets __body_override__ and __is_body_override__ when body() is present.
- __body_override__ is NOT set when the extension has no body() method.
- Four TypeError guards fire correctly.
- DataModelFactory._convert_action_body() picks up the override and sets
  DataTypeAction.body_override_source.
- Multiple conflicting body overrides raise TypeError.
- body_override_source is None when no override is loaded.
"""
from __future__ import annotations

import pytest
import zuspec.dataclasses as zdc


# ---------------------------------------------------------------------------
# Helper: minimal ConversionScope for direct calls to _convert_action_body
# ---------------------------------------------------------------------------

def _make_outer_scope():
    from zuspec.dataclasses.data_model_factory import ConversionScope
    return ConversionScope()


# ===========================================================================
# Decorator-level tests (no DataModelFactory needed)
# ===========================================================================

def test_extend_sets_body_override_attribute():
    """@zdc.extend with body() sets __body_override__ and __is_body_override__."""
    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _BaseAction(zdc.Action[_Comp]):
        async def body(self):
            pass

    @zdc.extend
    class _EcoAction(_BaseAction):
        async def body(self):
            pass

    assert _EcoAction.__is_body_override__ is True
    assert callable(_EcoAction.__body_override__)
    assert _EcoAction.__body_override__ is _EcoAction.__dict__['body']


def test_extend_body_override_not_set_without_body():
    """@zdc.extend with only a field (no body()) does NOT set __body_override__."""
    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _BaseAction(zdc.Action[_Comp]):
        async def body(self):
            pass

    @zdc.extend
    class _FieldExt(_BaseAction):
        tag: zdc.u4 = zdc.rand()

    assert not hasattr(_FieldExt, '__body_override__')
    assert not getattr(_FieldExt, '__is_body_override__', False)


def test_extend_body_and_activity_raises_type_error():
    """@zdc.extend defining both body() and activity() raises TypeError."""
    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _Base(zdc.Action[_Comp]):
        async def body(self):
            pass

    with pytest.raises(TypeError, match="both activity\\(\\) and body\\(\\)"):
        @zdc.extend
        class _BadExt(_Base):
            async def activity(self):
                pass

            async def body(self):
                pass


def test_extend_body_override_on_compound_action_raises_type_error():
    """@zdc.extend defining body() for an activity()-only base raises TypeError."""
    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _Sub(zdc.Action[_Comp]):
        async def body(self):
            pass

    @zdc.dataclass
    class _Compound(zdc.Action[_Comp]):
        sub: _Sub = zdc.field(default=None)

        async def activity(self):
            await self.sub()

    with pytest.raises(TypeError, match="compound action"):
        @zdc.extend
        class _BadExt(_Compound):
            async def body(self):
                pass


def test_extend_field_only_extension_unaffected_by_body_override_detection():
    """A field-only @zdc.extend coexists cleanly with a body-override extension."""
    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _Base(zdc.Action[_Comp]):
        async def body(self):
            pass

    @zdc.extend
    class _FieldExt(_Base):
        extra: zdc.u8 = zdc.rand()

    @zdc.extend
    class _BodyExt(_Base):
        async def body(self):
            pass

    # Field extension: no body override attributes
    assert not getattr(_FieldExt, '__is_body_override__', False)
    # Body extension: has body override attributes
    assert _BodyExt.__is_body_override__ is True


# ===========================================================================
# DataModelFactory-level tests
# ===========================================================================

def test_extend_body_override_source_set_in_ir():
    """DataModelFactory sets body_override_source on DataTypeAction when override present.

    The test calls _convert_action_body directly to trigger override detection.
    body_override_source is set even if inspect.getsource() cannot parse the body
    (the source recording happens before the parsing attempt).
    """
    from zuspec.dataclasses.data_model_factory import DataModelFactory

    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _BaseAction(zdc.Action[_Comp]):
        async def body(self):
            pass  # original body (would be buggy in a real ECO)

    @zdc.extend
    class _EcoFix(_BaseAction):
        async def body(self):
            pass  # corrected body

    factory = DataModelFactory()
    ctx = factory.build([_BaseAction])

    # Trigger body conversion (sets body_override_source as a side effect)
    factory._convert_action_body(
        action_cls=_BaseAction,
        result_var="rv",
        action_field_names=set(),
        local_prefix="rv_",
        comp_field_indices={},
        outer_scope=_make_outer_scope(),
    )

    type_name = factory._get_type_name(_BaseAction)
    action_dt = ctx.type_m.get(type_name)
    assert action_dt is not None, f"Action not in context. Keys: {list(ctx.type_m.keys())}"
    assert action_dt.body_override_source == '_EcoFix', (
        f"Expected body_override_source='_EcoFix', got {action_dt.body_override_source!r}"
    )


def test_data_model_factory_raises_on_multiple_body_overrides():
    """DataModelFactory raises TypeError when two extensions override body()."""
    from zuspec.dataclasses.data_model_factory import DataModelFactory

    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _Base(zdc.Action[_Comp]):
        async def body(self):
            pass

    @zdc.extend
    class _Override1(_Base):
        async def body(self):
            pass

    @zdc.extend
    class _Override2(_Base):
        async def body(self):
            pass

    factory = DataModelFactory()
    factory.build([_Base])

    with pytest.raises(TypeError, match="Multiple @zdc.extend"):
        factory._convert_action_body(
            action_cls=_Base,
            result_var="rv",
            action_field_names=set(),
            local_prefix="rv_",
            comp_field_indices={},
            outer_scope=_make_outer_scope(),
        )


def test_body_override_source_is_none_without_extension():
    """DataTypeAction.body_override_source is None when no extension is loaded."""
    from zuspec.dataclasses.data_model_factory import DataModelFactory

    @zdc.dataclass
    class _Comp(zdc.Component):
        pass

    @zdc.dataclass
    class _PlainAction(zdc.Action[_Comp]):
        async def body(self):
            pass

    factory = DataModelFactory()
    ctx = factory.build([_PlainAction])

    # Trigger body conversion
    factory._convert_action_body(
        action_cls=_PlainAction,
        result_var="rv",
        action_field_names=set(),
        local_prefix="rv_",
        comp_field_indices={},
        outer_scope=_make_outer_scope(),
    )

    type_name = factory._get_type_name(_PlainAction)
    action_dt = ctx.type_m.get(type_name)
    assert action_dt is not None
    assert action_dt.body_override_source is None


def test_body_override_source_field_exists_on_data_type_action():
    """DataTypeAction has the body_override_source field with default None."""
    from zuspec.dataclasses.ir.data_type import DataTypeAction

    dt = DataTypeAction(super=None)
    assert hasattr(dt, 'body_override_source')
    assert dt.body_override_source is None
