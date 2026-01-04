"""Test parameterized types with const fields and width specifications"""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.dataclasses.ir.data_type import DataTypeComponent, DataTypeInt
from zuspec.dataclasses.ir.fields import Field, FieldKind


def test_const_field_declaration():
    """Test that const fields can be declared with defaults"""
    
    @zdc.dataclass
    class ParamBundle(zdc.Bundle):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        ADDR_WIDTH : zdc.u32 = zdc.const(default=64)
        data : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
        addr : zdc.bitv = zdc.output(width=lambda s:s.ADDR_WIDTH)
    
    # Verify const fields exist
    assert hasattr(ParamBundle, '__dataclass_fields__')
    assert 'DATA_WIDTH' in ParamBundle.__dataclass_fields__
    assert 'ADDR_WIDTH' in ParamBundle.__dataclass_fields__
    
    # Verify const metadata
    data_width_field = ParamBundle.__dataclass_fields__['DATA_WIDTH']
    assert data_width_field.metadata.get('kind') == 'const'
    assert data_width_field.default == 32


def test_width_lambda_with_const():
    """Test field widths specified via lambda referencing const fields"""
    
    @zdc.dataclass
    class WidthParamBundle(zdc.Bundle):
        WIDTH : zdc.u32 = zdc.const(default=16)
        signal : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
    
    # Verify width metadata is stored
    signal_field = WidthParamBundle.__dataclass_fields__['signal']
    assert 'width' in signal_field.metadata
    assert callable(signal_field.metadata['width'])


def test_kwargs_lambda_for_bundle():
    """Test bundle instantiation with kwargs lambda for parameterization"""
    
    @zdc.dataclass
    class SimpleBundle(zdc.Bundle):
        WIDTH : zdc.u32 = zdc.const(default=8)
        data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
    
    @zdc.dataclass
    class ParamComponent(zdc.Component):
        BUS_WIDTH : zdc.u32 = zdc.const(default=32)
        bus : SimpleBundle = zdc.bundle(
            kwargs=lambda s:dict(WIDTH=s.BUS_WIDTH))
    
    # Verify kwargs metadata is stored
    bus_field = ParamComponent.__dataclass_fields__['bus']
    assert 'kwargs' in bus_field.metadata
    assert callable(bus_field.metadata['kwargs'])


def test_multiple_const_params():
    """Test component with multiple const parameters"""
    
    @zdc.dataclass
    class MultiParamBundle(zdc.Bundle):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
        TAG_WIDTH : zdc.u32 = zdc.const(default=8)
        
        data : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
        addr : zdc.bitv = zdc.output(width=lambda s:s.ADDR_WIDTH)
        tag : zdc.bitv = zdc.output(width=lambda s:s.TAG_WIDTH)
    
    assert MultiParamBundle.__dataclass_fields__['DATA_WIDTH'].default == 32
    assert MultiParamBundle.__dataclass_fields__['ADDR_WIDTH'].default == 32
    assert MultiParamBundle.__dataclass_fields__['TAG_WIDTH'].default == 8


def test_computed_width_from_const():
    """Test field width computed from const (e.g., DATA_WIDTH/8 for byte enables)"""
    
    @zdc.dataclass
    class ByteEnableBundle(zdc.Bundle):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        data : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
        strobe : zdc.bitv = zdc.output(width=lambda s:int(s.DATA_WIDTH/8))
    
    # Verify both fields have width lambdas
    data_field = ByteEnableBundle.__dataclass_fields__['data']
    strobe_field = ByteEnableBundle.__dataclass_fields__['strobe']
    
    assert callable(data_field.metadata['width'])
    assert callable(strobe_field.metadata['width'])


def test_nested_parameterized_bundles():
    """Test component with nested parameterized bundle instances"""
    
    @zdc.dataclass
    class DataBus(zdc.Bundle):
        WIDTH : zdc.u32 = zdc.const(default=16)
        data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
        valid : zdc.bit = zdc.output()
    
    @zdc.dataclass
    class DualBusComponent(zdc.Component):
        BUS_A_WIDTH : zdc.u32 = zdc.const(default=32)
        BUS_B_WIDTH : zdc.u32 = zdc.const(default=64)
        
        bus_a : DataBus = zdc.bundle(kwargs=lambda s:dict(WIDTH=s.BUS_A_WIDTH))
        bus_b : DataBus = zdc.bundle(kwargs=lambda s:dict(WIDTH=s.BUS_B_WIDTH))
    
    # Verify both bundles have kwargs
    assert 'kwargs' in DualBusComponent.__dataclass_fields__['bus_a'].metadata
    assert 'kwargs' in DualBusComponent.__dataclass_fields__['bus_b'].metadata


def test_const_in_packed_struct():
    """Test const fields in PackedStruct (like ReqData/RspData in initiator.py)"""
    
    @zdc.dataclass
    class ParamStruct(zdc.PackedStruct):
        WIDTH : zdc.u32 = zdc.const(default=32)
        data : zdc.bitv = zdc.field(width=lambda s:s.WIDTH)
        valid : zdc.bit = zdc.field()
    
    # Verify const field
    width_field = ParamStruct.__dataclass_fields__['WIDTH']
    assert width_field.metadata.get('kind') == 'const'
    assert width_field.default == 32


def test_inst_with_elem_factory_kwargs():
    """Test inst() with elem_factory using const parameters"""
    
    @zdc.dataclass
    class Message(zdc.PackedStruct):
        WIDTH : zdc.u32 = zdc.const(default=16)
        payload : zdc.bitv = zdc.field(width=lambda s:s.WIDTH)
    
    @zdc.dataclass
    class FifoComponent(zdc.Component):
        MSG_WIDTH : zdc.u32 = zdc.const(default=32)
        
        # Note: In initiator.py, elem_factory is used with FifoRV
        # This tests the pattern of passing const params to element factory
        messages : tuple[Message, ...] = zdc.tuple(
            size=4,
            elem_factory=lambda s: Message(WIDTH=s.MSG_WIDTH))
    
    # Verify tuple metadata
    messages_field = FifoComponent.__dataclass_fields__['messages']
    assert messages_field.metadata.get('size') == 4
    assert 'elem_factory' in messages_field.metadata


def test_datamodel_factory_extracts_const_fields():
    """Test that DataModelFactory extracts const fields into IR"""
    
    @zdc.dataclass
    class SimpleParam(zdc.Component):
        WIDTH : zdc.u32 = zdc.const(default=32)
        data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
    
    factory = DataModelFactory()
    context = factory.build(SimpleParam)
    
    # Verify type was added to context (using qualified name)
    type_name = list(context.type_m.keys())[0]
    assert 'SimpleParam' in type_name
    
    component_dm = context.type_m[type_name]
    assert isinstance(component_dm, DataTypeComponent)
    
    # Find the WIDTH field
    width_field = next((f for f in component_dm.fields if f.name == 'WIDTH'), None)
    assert width_field is not None
    assert isinstance(width_field.datatype, DataTypeInt)
    
    # Find the data field
    data_field = next((f for f in component_dm.fields if f.name == 'data'), None)
    assert data_field is not None


def test_datamodel_factory_preserves_width_metadata():
    """Test that DataModelFactory preserves width specifications in IR"""
    
    @zdc.dataclass
    class WidthBundle(zdc.Bundle):
        SIZE : zdc.u32 = zdc.const(default=16)
        signal : zdc.bitv = zdc.output(width=lambda s:s.SIZE)
    
    factory = DataModelFactory()
    context = factory.build(WidthBundle)
    
    type_name = list(context.type_m.keys())[0]
    assert 'WidthBundle' in type_name
    bundle_dm = context.type_m[type_name]
    
    # Verify const field
    size_field = next((f for f in bundle_dm.fields if f.name == 'SIZE'), None)
    assert size_field is not None
    
    # Verify signal field exists (width handling TBD in IR enhancement)
    signal_field = next((f for f in bundle_dm.fields if f.name == 'signal'), None)
    assert signal_field is not None


def test_datamodel_factory_preserves_kwargs_metadata():
    """Test that DataModelFactory preserves kwargs for bundle instantiation"""
    
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
    
    type_name = list(context.type_m.keys())[0]
    assert 'Outer' in type_name
    outer_dm = context.type_m[type_name]
    
    # Find inner bundle field
    inner_field = next((f for f in outer_dm.fields if f.name == 'inner'), None)
    assert inner_field is not None
    # Note: kwargs handling in IR is part of enhancement


def test_wishbone_initiator_pattern():
    """Test the full Wishbone initiator pattern from initiator.py"""
    
    @zdc.dataclass
    class WishboneInitiator(zdc.Bundle):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
        adr : zdc.bitv = zdc.output(width=lambda s:s.ADDR_WIDTH)
        dat_w : zdc.bitv = zdc.output(width=lambda s:s.DATA_WIDTH)
        dat_r : zdc.bitv = zdc.input(width=lambda s:s.DATA_WIDTH)
        sel : zdc.bitv = zdc.input(width=lambda s:int(s.DATA_WIDTH/8))
        cyc : zdc.bit = zdc.output()
        we : zdc.bit = zdc.output()
    
    @zdc.dataclass
    class InitiatorCore(zdc.Component):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
        
        init : WishboneInitiator = zdc.bundle(
            kwargs=lambda s:dict(DATA_WIDTH=s.DATA_WIDTH, ADDR_WIDTH=s.ADDR_WIDTH))
    
    # Verify the bundle field is declared
    assert 'init' in InitiatorCore.__dataclass_fields__
    init_field = InitiatorCore.__dataclass_fields__['init']
    assert 'kwargs' in init_field.metadata
    
    # Test with DataModelFactory
    factory = DataModelFactory()
    context = factory.build([WishboneInitiator, InitiatorCore])
    
    # Find types by name substring (they use qualified names)
    wb_type = next((k for k in context.type_m.keys() if 'WishboneInitiator' in k), None)
    core_type = next((k for k in context.type_m.keys() if 'InitiatorCore' in k), None)
    
    assert wb_type is not None
    assert core_type is not None


def test_ir_captures_width_expressions():
    """Test that IR captures width expressions as ExprLambda"""
    from zuspec.dataclasses.ir.expr import ExprLambda
    
    @zdc.dataclass
    class ParamBundle(zdc.Bundle):
        WIDTH : zdc.u32 = zdc.const(default=16)
        signal : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
    
    factory = DataModelFactory()
    context = factory.build(ParamBundle)
    
    type_name = list(context.type_m.keys())[0]
    bundle_dm = context.type_m[type_name]
    
    # Find WIDTH field and verify it's marked as const
    width_field = next((f for f in bundle_dm.fields if f.name == 'WIDTH'), None)
    assert width_field is not None
    assert width_field.is_const is True
    
    # Find signal field and verify width_expr is captured
    signal_field = next((f for f in bundle_dm.fields if f.name == 'signal'), None)
    assert signal_field is not None
    assert signal_field.width_expr is not None
    assert isinstance(signal_field.width_expr, ExprLambda)
    assert callable(signal_field.width_expr.callable)


def test_ir_captures_kwargs_expressions():
    """Test that IR captures kwargs expressions as ExprLambda"""
    from zuspec.dataclasses.ir.expr import ExprLambda
    
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
    
    # Find inner field and verify kwargs_expr is captured
    inner_field = next((f for f in outer_dm.fields if f.name == 'inner'), None)
    assert inner_field is not None
    assert inner_field.kwargs_expr is not None
    assert isinstance(inner_field.kwargs_expr, ExprLambda)
    assert callable(inner_field.kwargs_expr.callable)
