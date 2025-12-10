import asyncio
import zuspec.dataclasses as zdc
from typing import Final, Protocol

def test_smoke():

    class DataIF(Protocol):
        async def call(self, req : int) -> int: ...

    @zdc.dataclass
    class MyProdC(zdc.Component):
        prod : DataIF = zdc.port()

        @zdc.process
        async def _run(self):
            for i in range(16):
                rsp = await self.prod.call(i)

    @zdc.dataclass
    class MyConsC(zdc.Component):
        # Bind, in this context, must work in one of two ways
        # -  
        cons : DataIF = zdc.export()

        def __bind__(self): return {
            self.cons.call : self.target
        }

        async def target(self, req : int) -> int:
            print("-- target")
            await self.wait(zdc.Time.ns(10))
            return req+2

    @zdc.dataclass
    class MyC(zdc.Component):
        p : MyProdC = zdc.field() # default_factory=MySubC)
        c : MyConsC = zdc.field()

        def __post_init__(self):
            print("MyC.__post_init__: %s" % str(self), flush=True)
#            super().__post_init__()

        def __bind__(self): return {
            self.p.prod : self.c.cons
        }

    print("--> MyC()")
    c = MyC()
    print("<-- MyC()")

    # Run simulation for enough time to complete all 16 iterations (16 * 10ns = 160ns)
    asyncio.run(c.wait(zdc.Time.ns(200)))

def test_method_call():

    class DataIF(Protocol):
        async def call(self, req : int) -> int: ...

    @zdc.dataclass
    class MyProdC(zdc.Component):
        prod : DataIF = zdc.port()

#        @zdc.process
#        async def _run(self):
#            for i in range(16):
#                rsp = await self.prod.call(i)

    @zdc.dataclass
    class MyConsC(zdc.Component):
        # Bind, in this context, must work in one of two ways
        # -  
        cons : DataIF = zdc.export()

        def __bind__(self): return {
            self.cons.call : self.target
        }

        async def target(self, req : int) -> int:
            print("-- target")
            await self.wait(zdc.Time.ns(10))
            return req+2

    @zdc.dataclass
    class MyC(zdc.Component):
        p : MyProdC = zdc.field() # default_factory=MySubC)
        c : MyConsC = zdc.field()

        def __post_init__(self):
            print("MyC.__post_init__: %s" % str(self), flush=True)
#            super().__post_init__()

        def __bind__(self): return {
            self.p.prod : self.c.cons
        }

    print("--> MyC()")
    c = MyC()
    print("<-- MyC()")

    async def run():
        for i in range(16):
            await c.c.target(i)

    # Run simulation for enough time to complete all 16 iterations (16 * 10ns = 160ns)
    asyncio.run(run())

def test_top_if():
    """Test that top-level unbound ports fail with a clear error message."""

    class MemIF(Protocol):
        async def read(self, addr : int) -> int: ...

        async def write(self, addr : int, data : int): ...

    @zdc.dataclass
    class MyC(zdc.Component):
        m0 : MemIF = zdc.port()

        @zdc.process
        async def _run(self):
            for i in range(16):
                await self.m0.write(4*i, i+1)
                val = await self.m0.read(4*i)

    # This should fail because m0 is unbound
    import pytest
    with pytest.raises(RuntimeError, match="unbound ports.*m0"):
        o = MyC()


def test_top_if_with_impl():
    """Test that top-level ports can be bound via constructor argument."""

    class MemIF(Protocol):
        async def read(self, addr : int) -> int: ...

        async def write(self, addr : int, data : int): ...

    # Track calls to read/write
    write_calls = []
    read_calls = []

    class MemImpl:
        """Implementation of MemIF protocol"""
        def __init__(self):
            self.mem = {}

        async def read(self, addr: int) -> int:
            read_calls.append(addr)
            return self.mem.get(addr, 0)

        async def write(self, addr: int, data: int):
            write_calls.append((addr, data))
            self.mem[addr] = data

    @zdc.dataclass
    class MyC(zdc.Component):
        m0 : MemIF = zdc.port()

        @zdc.process
        async def _run(self):
            for i in range(16):
                await self.m0.write(4*i, i+1)
                val = await self.m0.read(4*i)

    # Create component with bound port
    mem_impl = MemImpl()
    o = MyC(m0=mem_impl)

    asyncio.run(o.wait(zdc.Time.us(10)))

    # Verify read and write were invoked properly
    assert len(write_calls) == 16, f"Expected 16 write calls, got {len(write_calls)}"
    assert len(read_calls) == 16, f"Expected 16 read calls, got {len(read_calls)}"
    
    # Verify write calls: write(4*i, i+1) for i in 0..15
    for i in range(16):
        assert write_calls[i] == (4*i, i+1), f"Write call {i} mismatch: {write_calls[i]}"
    
    # Verify read calls: read(4*i) for i in 0..15
    for i in range(16):
        assert read_calls[i] == 4*i, f"Read call {i} mismatch: {read_calls[i]}"

    o.shutdown()

def test_component_datamodel():
    """Test that top-level ports can be bound via constructor argument."""
    import zuspec.dataclasses.dm as dm

    class MemIF(Protocol):
        async def read(self, addr : int) -> int: ...

        async def write(self, addr : int, data : int): ...

    @zdc.dataclass
    class MyC(zdc.Component):
        m0 : MemIF = zdc.port()

        @zdc.process
        async def _run(self):
            for i in range(16):
                await self.m0.write(4*i, i+1)
                val = await self.m0.read(4*i)

    dm_ctxt = zdc.DataModelFactory().build(MyC)

    # Types are keyed by their __qualname__ in the context
    memif_qualname = MemIF.__qualname__
    myc_qualname = MyC.__qualname__

    # Verify Context contains expected types by qualname
    assert memif_qualname in dm_ctxt.type_m, \
        f"MemIF ({memif_qualname}) should be in context"
    assert myc_qualname in dm_ctxt.type_m, \
        f"MyC ({myc_qualname}) should be in context"
    
    memif_dm = dm_ctxt.type_m[memif_qualname]
    myc_dm = dm_ctxt.type_m[myc_qualname]
    
    # Verify data model name matches qualname
    assert memif_dm.name == memif_qualname, \
        f"MemIF data model name should be '{memif_qualname}', got '{memif_dm.name}'"
    assert myc_dm.name == myc_qualname, \
        f"MyC data model name should be '{myc_qualname}', got '{myc_dm.name}'"

    # Verify MemIF is a DataTypeProtocol with two methods
    assert isinstance(memif_dm, dm.DataTypeProtocol), \
        f"MemIF should be DataTypeProtocol, got {type(memif_dm).__name__}"
    assert len(memif_dm.methods) == 2, \
        f"MemIF should have 2 methods, got {len(memif_dm.methods)}"
    
    method_names = {m.name for m in memif_dm.methods}
    assert 'read' in method_names, "MemIF should have 'read' method"
    assert 'write' in method_names, "MemIF should have 'write' method"
    
    # Verify methods are async
    for method in memif_dm.methods:
        assert method.is_async, f"Method {method.name} should be async"

    # Verify MyC is a DataTypeComponent
    assert isinstance(myc_dm, dm.DataTypeComponent), \
        f"MyC should be DataTypeComponent, got {type(myc_dm).__name__}"

    # Verify MyC has a field m0 of kind port with type MemIF
    assert len(myc_dm.fields) >= 1, "MyC should have at least 1 field"
    m0_field = None
    for f in myc_dm.fields:
        if f.name == 'm0':
            m0_field = f
            break
    assert m0_field is not None, "MyC should have field 'm0'"
    assert m0_field.kind == dm.FieldKind.Port, \
        f"Field m0 should be Port, got {m0_field.kind}"
    assert isinstance(m0_field.datatype, dm.DataTypeRef), \
        f"Field m0 datatype should be DataTypeRef, got {type(m0_field.datatype).__name__}"
    assert m0_field.datatype.ref_name == 'MemIF', \
        f"Field m0 should reference MemIF, got {m0_field.datatype.ref_name}"

    # Verify MyC has a Process element named _run
    process_found = False
    for func in myc_dm.functions:
        if isinstance(func, dm.Process) and func.name == '_run':
            process_found = True
            break
    assert process_found, "MyC should have a Process named '_run'"

    # Use Visitor to walk through the data model and verify structure
    @dm.visitor(dm)
    class DataModelValidator(dm.Visitor):
        def __init__(self, pmod=None):
            self.visited_protocols = []
            self.visited_components = []
            self.visited_fields = []
            self.visited_processes = []
            self.visited_for_loops = []

        def visitDataTypeProtocol(self, o: dm.DataTypeProtocol):
            self.visited_protocols.append(o)
            # Visit methods
            for method in o.methods:
                method.accept(self)

        def visitDataTypeComponent(self, o: dm.DataTypeComponent):
            self.visited_components.append(o)
            # Visit fields
            for field in o.fields:
                field.accept(self)
            # Visit functions/processes
            for func in o.functions:
                func.accept(self)

        def visitField(self, o: dm.Field):
            self.visited_fields.append(o)

        def visitProcess(self, o: dm.Process):
            self.visited_processes.append(o)
            # Visit body statements
            for stmt in o.body:
                stmt.accept(self)

        def visitStmtFor(self, o: dm.StmtFor):
            self.visited_for_loops.append(o)

    validator = DataModelValidator()
    
    # Visit each type in the context
    for type_name, type_dm in dm_ctxt.type_m.items():
        type_dm.accept(validator)

    # Verify visitor found expected elements
    assert len(validator.visited_protocols) == 1, \
        f"Should visit 1 protocol, visited {len(validator.visited_protocols)}"
    assert len(validator.visited_components) == 1, \
        f"Should visit 1 component, visited {len(validator.visited_components)}"
    assert len(validator.visited_processes) == 1, \
        f"Should visit 1 process, visited {len(validator.visited_processes)}"
    
    # Verify the port field was visited
    port_fields = [f for f in validator.visited_fields if f.kind == dm.FieldKind.Port]
    assert len(port_fields) == 1, \
        f"Should visit 1 port field, visited {len(port_fields)}"






