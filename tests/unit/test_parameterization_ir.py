"""Test IR representation of parameterized types"""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.dataclasses.ir.data_type import DataTypeComponent, DataTypeInt
from zuspec.dataclasses.ir.expr import ExprLambda
from zuspec.dataclasses.ir.fields import Field, FieldInOut


def test_ir_field_metadata_complete():
    """Test complete IR metadata for parameterized fields"""
    
    @zdc.dataclass
    class ParameterizedBundle(zdc.Bundle):
        # Const parameters
        WIDTH : zdc.u32 = zdc.const(default=32)
        DEPTH : zdc.u32 = zdc.const(default=16)
        
        # Field with width expression
        data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
        
        # Field with computed width
        strobe : zdc.bitv = zdc.output(width=lambda s:int(s.WIDTH/8))
        
        # Fixed width field
        valid : zdc.bit = zdc.output()
    
    factory = DataModelFactory()
    context = factory.build(ParameterizedBundle)
    
    type_name = list(context.type_m.keys())[0]
    bundle_dm = context.type_m[type_name]
    
    # Check WIDTH field (const)
    width_field = next((f for f in bundle_dm.fields if f.name == 'WIDTH'), None)
    assert width_field is not None
    assert width_field.is_const is True
    assert isinstance(width_field.datatype, DataTypeInt)
    assert width_field.datatype.bits == 32
    assert width_field.datatype.signed is False
    assert width_field.width_expr is None  # Const fields don't have width_expr
    assert width_field.kwargs_expr is None
    
    # Check DEPTH field (const)
    depth_field = next((f for f in bundle_dm.fields if f.name == 'DEPTH'), None)
    assert depth_field is not None
    assert depth_field.is_const is True
    
    # Check data field (parameterized width)
    data_field = next((f for f in bundle_dm.fields if f.name == 'data'), None)
    assert data_field is not None
    assert isinstance(data_field, FieldInOut)
    assert data_field.is_out is True
    assert data_field.is_const is False
    assert data_field.width_expr is not None
    assert isinstance(data_field.width_expr, ExprLambda)
    assert callable(data_field.width_expr.callable)
    assert data_field.kwargs_expr is None
    
    # Check strobe field (computed width)
    strobe_field = next((f for f in bundle_dm.fields if f.name == 'strobe'), None)
    assert strobe_field is not None
    assert isinstance(strobe_field, FieldInOut)
    assert strobe_field.is_out is True
    assert strobe_field.width_expr is not None
    assert isinstance(strobe_field.width_expr, ExprLambda)
    
    # Check valid field (fixed width)
    valid_field = next((f for f in bundle_dm.fields if f.name == 'valid'), None)
    assert valid_field is not None
    assert isinstance(valid_field, FieldInOut)
    assert valid_field.is_out is True
    assert valid_field.width_expr is None  # Fixed width, no expression


def test_ir_nested_kwargs():
    """Test IR representation of nested parameterized bundles"""
    
    @zdc.dataclass
    class DataBus(zdc.Bundle):
        BUS_WIDTH : zdc.u32 = zdc.const(default=8)
        data : zdc.bitv = zdc.output(width=lambda s:s.BUS_WIDTH)
        valid : zdc.bit = zdc.output()
    
    @zdc.dataclass
    class DualBusComponent(zdc.Component):
        PRIMARY_WIDTH : zdc.u32 = zdc.const(default=32)
        SECONDARY_WIDTH : zdc.u32 = zdc.const(default=16)
        
        primary_bus : DataBus = zdc.bundle(
            kwargs=lambda s:dict(BUS_WIDTH=s.PRIMARY_WIDTH))
        
        secondary_bus : DataBus = zdc.bundle(
            kwargs=lambda s:dict(BUS_WIDTH=s.SECONDARY_WIDTH))
    
    factory = DataModelFactory()
    context = factory.build([DataBus, DualBusComponent])
    
    # Find component type
    comp_type = next((k for k in context.type_m.keys() if 'DualBusComponent' in k), None)
    assert comp_type is not None
    comp_dm = context.type_m[comp_type]
    
    # Check primary_bus field
    primary_field = next((f for f in comp_dm.fields if f.name == 'primary_bus'), None)
    assert primary_field is not None
    assert primary_field.kwargs_expr is not None
    assert isinstance(primary_field.kwargs_expr, ExprLambda)
    assert callable(primary_field.kwargs_expr.callable)
    
    # Check secondary_bus field
    secondary_field = next((f for f in comp_dm.fields if f.name == 'secondary_bus'), None)
    assert secondary_field is not None
    assert secondary_field.kwargs_expr is not None
    assert isinstance(secondary_field.kwargs_expr, ExprLambda)


def test_ir_packed_struct_with_params():
    """Test IR representation of PackedStruct with const parameters"""
    
    @zdc.dataclass
    class Message(zdc.PackedStruct):
        MSG_WIDTH : zdc.u32 = zdc.const(default=64)
        METADATA_WIDTH : zdc.u32 = zdc.const(default=8)
        
        payload : zdc.bitv = zdc.field(width=lambda s:s.MSG_WIDTH)
        metadata : zdc.bitv = zdc.field(width=lambda s:s.METADATA_WIDTH)
        valid : zdc.bit = zdc.field()
    
    factory = DataModelFactory()
    context = factory.build(Message)
    
    type_name = list(context.type_m.keys())[0]
    msg_dm = context.type_m[type_name]
    
    # Verify const fields
    msg_width_field = next((f for f in msg_dm.fields if f.name == 'MSG_WIDTH'), None)
    assert msg_width_field is not None
    assert msg_width_field.is_const is True
    
    metadata_width_field = next((f for f in msg_dm.fields if f.name == 'METADATA_WIDTH'), None)
    assert metadata_width_field is not None
    assert metadata_width_field.is_const is True
    
    # Verify parameterized fields
    payload_field = next((f for f in msg_dm.fields if f.name == 'payload'), None)
    assert payload_field is not None
    assert payload_field.width_expr is not None
    assert isinstance(payload_field.width_expr, ExprLambda)
    
    metadata_field = next((f for f in msg_dm.fields if f.name == 'metadata'), None)
    assert metadata_field is not None
    assert metadata_field.width_expr is not None
    assert isinstance(metadata_field.width_expr, ExprLambda)


def test_ir_lambda_evaluation():
    """Test that lambdas can be evaluated with mock instance"""
    
    @zdc.dataclass
    class Parameterized(zdc.Bundle):
        WIDTH : zdc.u32 = zdc.const(default=32)
        data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
    
    factory = DataModelFactory()
    context = factory.build(Parameterized)
    
    type_name = list(context.type_m.keys())[0]
    bundle_dm = context.type_m[type_name]
    
    # Get width lambda
    data_field = next((f for f in bundle_dm.fields if f.name == 'data'), None)
    assert data_field.width_expr is not None
    width_lambda = data_field.width_expr.callable
    
    # Create a mock instance with WIDTH attribute
    class MockInstance:
        WIDTH = 64
    
    mock = MockInstance()
    
    # Evaluate lambda
    computed_width = width_lambda(mock)
    assert computed_width == 64
    
    # Test with different width
    mock.WIDTH = 128
    computed_width = width_lambda(mock)
    assert computed_width == 128


def test_ir_kwargs_evaluation():
    """Test that kwargs lambdas can be evaluated"""
    
    @zdc.dataclass
    class Inner(zdc.Bundle):
        W : zdc.u32 = zdc.const(default=8)
        data : zdc.bitv = zdc.output(width=lambda s:s.W)
    
    @zdc.dataclass
    class Outer(zdc.Component):
        WIDTH : zdc.u32 = zdc.const(default=32)
        inner : Inner = zdc.bundle(kwargs=lambda s:dict(W=s.WIDTH))
    
    factory = DataModelFactory()
    context = factory.build(Outer)
    
    type_name = next((k for k in context.type_m.keys() if 'Outer' in k), None)
    outer_dm = context.type_m[type_name]
    
    # Get kwargs lambda
    inner_field = next((f for f in outer_dm.fields if f.name == 'inner'), None)
    assert inner_field.kwargs_expr is not None
    kwargs_lambda = inner_field.kwargs_expr.callable
    
    # Create mock instance
    class MockOuter:
        WIDTH = 64
    
    mock = MockOuter()
    
    # Evaluate kwargs lambda
    kwargs_dict = kwargs_lambda(mock)
    assert isinstance(kwargs_dict, dict)
    assert 'W' in kwargs_dict
    assert kwargs_dict['W'] == 64


def test_ir_multiple_const_types():
    """Test IR with different const field types"""
    
    @zdc.dataclass
    class MultiParam(zdc.Component):
        WIDTH : zdc.u32 = zdc.const(default=32)
        DEPTH : zdc.u16 = zdc.const(default=256)
        ENABLE : zdc.bit = zdc.const(default=1)
        
        data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
    
    factory = DataModelFactory()
    context = factory.build(MultiParam)
    
    type_name = list(context.type_m.keys())[0]
    comp_dm = context.type_m[type_name]
    
    # Check WIDTH (u32)
    width_field = next((f for f in comp_dm.fields if f.name == 'WIDTH'), None)
    assert width_field is not None
    assert width_field.is_const is True
    assert isinstance(width_field.datatype, DataTypeInt)
    assert width_field.datatype.bits == 32
    
    # Check DEPTH (u16)
    depth_field = next((f for f in comp_dm.fields if f.name == 'DEPTH'), None)
    assert depth_field is not None
    assert depth_field.is_const is True
    assert isinstance(depth_field.datatype, DataTypeInt)
    assert depth_field.datatype.bits == 16
    
    # Check ENABLE (bit)
    enable_field = next((f for f in comp_dm.fields if f.name == 'ENABLE'), None)
    assert enable_field is not None
    assert enable_field.is_const is True
    assert isinstance(enable_field.datatype, DataTypeInt)
    assert enable_field.datatype.bits == 1
