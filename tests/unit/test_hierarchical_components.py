"""Test hierarchical component construction.

This test suite validates that component fields are automatically constructed
when their type is a Component subclass.
"""
import asyncio
import zuspec.dataclasses as zdc
from typing import Protocol


def test_hierarchical_construction_basic():
    """Test basic hierarchical component construction."""
    
    @zdc.dataclass
    class LeafComponent(zdc.Component):
        value: zdc.bit32 = zdc.field(default=0)
        
    @zdc.dataclass
    class ParentComponent(zdc.Component):
        child: LeafComponent = zdc.field()
        
    # Create parent - child should be automatically constructed
    parent = ParentComponent()
    
    # Verify child was automatically created
    assert parent.child is not None
    assert isinstance(parent.child, LeafComponent)
    assert parent.child.value == 0


def test_hierarchical_construction_multiple_children():
    """Test hierarchical construction with multiple child components."""
    
    @zdc.dataclass
    class ChildA(zdc.Component):
        a_value: zdc.bit32 = zdc.field(default=10)
        
    @zdc.dataclass
    class ChildB(zdc.Component):
        b_value: zdc.bit32 = zdc.field(default=20)
        
    @zdc.dataclass
    class Parent(zdc.Component):
        child_a: ChildA = zdc.field()
        child_b: ChildB = zdc.field()
        
    parent = Parent()
    
    # Verify both children were automatically created
    assert parent.child_a is not None
    assert isinstance(parent.child_a, ChildA)
    assert parent.child_a.a_value == 10
    
    assert parent.child_b is not None
    assert isinstance(parent.child_b, ChildB)
    assert parent.child_b.b_value == 20


def test_hierarchical_construction_nested():
    """Test hierarchical construction with nested component hierarchies."""
    
    @zdc.dataclass
    class GrandChild(zdc.Component):
        gc_value: zdc.bit32 = zdc.field(default=100)
        
    @zdc.dataclass
    class Child(zdc.Component):
        grandchild: GrandChild = zdc.field()
        c_value: zdc.bit32 = zdc.field(default=50)
        
    @zdc.dataclass
    class Parent(zdc.Component):
        child: Child = zdc.field()
        
    parent = Parent()
    
    # Verify entire hierarchy was constructed
    assert parent.child is not None
    assert isinstance(parent.child, Child)
    assert parent.child.c_value == 50
    
    assert parent.child.grandchild is not None
    assert isinstance(parent.child.grandchild, GrandChild)
    assert parent.child.grandchild.gc_value == 100


def test_hierarchical_construction_with_ports():
    """Test hierarchical construction with port/export bindings."""
    
    class DataIF(Protocol):
        async def call(self, req: int) -> int: ...
        
    @zdc.dataclass
    class Producer(zdc.Component):
        prod: DataIF = zdc.port()
        
        @zdc.process
        async def _run(self):
            result = await self.prod.call(42)
            assert result == 44  # 42 + 2
            
    @zdc.dataclass
    class Consumer(zdc.Component):
        cons: DataIF = zdc.export()
        
        def __bind__(self):
            return {
                self.cons.call: self.target
            }
            
        async def target(self, req: int) -> int:
            await self.wait(zdc.Time.ns(10))
            return req + 2
            
    @zdc.dataclass
    class System(zdc.Component):
        producer: Producer = zdc.field()
        consumer: Consumer = zdc.field()
        
        def __bind__(self):
            return {
                self.producer.prod: self.consumer.cons
            }
            
    system = System()
    
    # Verify hierarchy was constructed
    assert system.producer is not None
    assert isinstance(system.producer, Producer)
    assert system.consumer is not None
    assert isinstance(system.consumer, Consumer)
    
    # Run simulation to verify port binding works
    asyncio.run(system.wait(zdc.Time.us(1)))
    
    system.shutdown()


def test_hierarchical_construction_with_sync_comb():
    """Test hierarchical construction with sync/comb processes."""
    
    @zdc.dataclass
    class ALU(zdc.Component):
        clk: zdc.bit = zdc.input()
        a: zdc.bit32 = zdc.input()
        b: zdc.bit32 = zdc.input()
        result: zdc.bit32 = zdc.output()
        
        @zdc.comb
        def _compute(self):
            self.result = (self.a + self.b) & 0xFFFFFFFF
            
    @zdc.dataclass
    class Datapath(zdc.Component):
        clk: zdc.bit = zdc.input()
        alu: ALU = zdc.field()
        
        def __bind__(self):
            return {
                self.alu.clk: self.clk
            }
            
    @zdc.dataclass
    class Processor(zdc.Component):
        clk: zdc.bit = zdc.input()
        datapath: Datapath = zdc.field()
        
        def __bind__(self):
            return {
                self.datapath.clk: self.clk
            }
            
    proc = Processor()
    
    # Verify hierarchy
    assert proc.datapath is not None
    assert isinstance(proc.datapath, Datapath)
    assert proc.datapath.alu is not None
    assert isinstance(proc.datapath.alu, ALU)
    
    # Test evaluation
    proc.clk = 0
    proc.datapath.alu.a = 10
    proc.datapath.alu.b = 20
    
    # Trigger evaluation
    proc.clk = 1
    
    # Result should be computed
    assert proc.datapath.alu.result == 30


def test_hierarchical_construction_datamodel():
    """Test that hierarchical components produce correct datamodel."""
    
    @zdc.dataclass
    class Child(zdc.Component):
        child_value: zdc.bit32 = zdc.field(default=0)
        
    @zdc.dataclass
    class Parent(zdc.Component):
        child: Child = zdc.field()
        parent_value: zdc.bit32 = zdc.field(default=0)
        
    # Build datamodel
    dm_ctxt = zdc.DataModelFactory().build(Parent)
    
    # Get component datamodel
    parent_qualname = Parent.__qualname__
    child_qualname = Child.__qualname__
    
    assert parent_qualname in dm_ctxt.type_m
    assert child_qualname in dm_ctxt.type_m
    
    parent_dm = dm_ctxt.type_m[parent_qualname]
    child_dm = dm_ctxt.type_m[child_qualname]
    
    # Verify Parent has a child field of type Child
    child_field = None
    for f in parent_dm.fields:
        if f.name == 'child':
            child_field = f
            break
            
    assert child_field is not None
    assert isinstance(child_field.datatype, zdc.dm.DataTypeRef)
    assert child_field.datatype.ref_name == 'Child'


def test_hierarchical_construction_with_explicit_default_factory():
    """Test that explicit default_factory is respected."""
    
    @zdc.dataclass
    class Child(zdc.Component):
        value: zdc.bit32 = zdc.field(default=0)
        
    @zdc.dataclass
    class Parent(zdc.Component):
        # Explicit default_factory should still work
        child: Child = zdc.field(default_factory=Child)
        
    parent = Parent()
    
    assert parent.child is not None
    assert isinstance(parent.child, Child)


def test_hierarchical_construction_post_init():
    """Test that __post_init__ is called correctly in hierarchical construction."""
    
    init_order = []
    
    @zdc.dataclass
    class Child(zdc.Component):
        value: zdc.bit32 = zdc.field(default=0)
        
        def __post_init__(self):
            init_order.append('child')
            
    @zdc.dataclass
    class Parent(zdc.Component):
        child: Child = zdc.field()
        
        def __post_init__(self):
            init_order.append('parent')
            
    parent = Parent()
    
    # Both __post_init__ should have been called
    assert 'child' in init_order
    assert 'parent' in init_order


def test_riscv_core_hierarchical_construction():
    """Test hierarchical construction with a realistic RISC-V core structure.
    
    This test validates the pattern used in riscv_core.py where subcomponents
    like FetchUnit, ControlUnit, and Datapath are declared as fields and
    automatically constructed.
    """
    
    @zdc.dataclass
    class FetchUnit(zdc.Component):
        clk: zdc.bit = zdc.input()
        pc: zdc.bit32 = zdc.output()
        
        @zdc.sync(clock=lambda self: self.clk, reset=None)
        def _fetch(self):
            self.pc = (self.pc + 4) & 0xFFFFFFFF
            
    @zdc.dataclass
    class ControlUnit(zdc.Component):
        opcode: zdc.bit8 = zdc.input()
        reg_write: zdc.bit = zdc.output()
        
        @zdc.comb
        def _decode(self):
            # Simple decode logic
            self.reg_write = 1 if (self.opcode & 0x7F) == 0x33 else 0
            
    @zdc.dataclass
    class ALU(zdc.Component):
        a: zdc.bit32 = zdc.input()
        b: zdc.bit32 = zdc.input()
        result: zdc.bit32 = zdc.output()
        
        @zdc.comb
        def _compute(self):
            self.result = (self.a + self.b) & 0xFFFFFFFF
            
    @zdc.dataclass
    class Datapath(zdc.Component):
        clk: zdc.bit = zdc.input()
        alu: ALU = zdc.field()
        
        def __bind__(self):
            return {}
            
    @zdc.dataclass
    class RiscvCore(zdc.Component):
        clk: zdc.bit = zdc.input()
        rst_n: zdc.bit = zdc.input()
        
        # Hierarchical subcomponents - automatically constructed
        u_fetch_unit: FetchUnit = zdc.field()
        u_control_unit: ControlUnit = zdc.field()
        u_datapath: Datapath = zdc.field()
        
        def __bind__(self):
            return {
                self.u_fetch_unit.clk: self.clk,
                self.u_datapath.clk: self.clk
            }
            
    # Create core - all subcomponents should be automatically constructed
    core = RiscvCore()
    
    # Verify hierarchy
    assert core.u_fetch_unit is not None
    assert isinstance(core.u_fetch_unit, FetchUnit)
    
    assert core.u_control_unit is not None
    assert isinstance(core.u_control_unit, ControlUnit)
    
    assert core.u_datapath is not None
    assert isinstance(core.u_datapath, Datapath)
    
    # Verify nested hierarchy
    assert core.u_datapath.alu is not None
    assert isinstance(core.u_datapath.alu, ALU)
    
    # Test that the hierarchy is functional
    core.clk = 0
    core.u_datapath.alu.a = 100
    core.u_datapath.alu.b = 200
    
    # Trigger evaluation
    core.clk = 1
    
    # ALU should compute result
    assert core.u_datapath.alu.result == 300
