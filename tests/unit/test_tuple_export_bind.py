"""
Tests for Tuple of exports with for-loop binding patterns.

These tests cover the patterns used in op_op_alg.py:
1. Creating a Tuple of exports: `req: Tuple[IReq, ...] = zdc.tuple(size=4, elem_factory=zdc.export)`
2. Using for loops with cast and bind to specify implementations for export element methods
"""

import asyncio
import zuspec.dataclasses as zdc
from typing import Protocol, Tuple, cast


class IReq(Protocol):
    """Protocol for request interface."""
    async def req_transfer(self) -> None: ...


@zdc.dataclass
class ReqImpl(zdc.Component):
    """Implementation component providing req_transfer."""
    _call_count: int = zdc.field(default=0)
    
    async def req_transfer(self) -> None:
        self._call_count += 1


@zdc.dataclass
class SimpleExportTuple(zdc.Component):
    """Component with a tuple of exports and matching implementations."""
    req: Tuple[IReq, ...] = zdc.tuple(size=2, elem_factory=zdc.export)
    channels: Tuple[ReqImpl, ...] = zdc.tuple(size=2, elem_factory=ReqImpl)
    
    def __bind__(self):
        ret = []
        for i in range(2):
            ret.append((
                self.req[i].req_transfer,
                cast(ReqImpl, self.channels[i]).req_transfer
            ))
        return tuple(ret)


class TestTupleExportRuntime:
    """Test runtime construction and binding of tuple exports."""
    
    def test_tuple_export_construction(self):
        """Test that a component with tuple of exports can be constructed."""
        comp = SimpleExportTuple()
        assert comp is not None
        assert comp.req is not None
        assert comp.channels is not None
        assert len(comp.req) == 2
        assert len(comp.channels) == 2
    
    def test_tuple_export_binding(self):
        """Test that export methods are bound to implementation methods."""
        comp = SimpleExportTuple()
        
        # Each export element should have req_transfer bound
        for i in range(2):
            assert hasattr(comp.req[i], 'req_transfer'), f"req[{i}] should have req_transfer"
            assert callable(comp.req[i].req_transfer), f"req[{i}].req_transfer should be callable"
    
    def test_tuple_export_call_through(self):
        """Test that calling export methods invokes the implementation."""
        async def _run():
            comp = SimpleExportTuple()
            
            # Call through each export
            for i in range(2):
                await comp.req[i].req_transfer()
            
            # Verify implementations were called
            for i in range(2):
                assert comp.channels[i]._call_count == 1, f"channels[{i}] should have been called once"
        
        asyncio.run(_run())


class IMultiMethod(Protocol):
    """Protocol with multiple methods."""
    async def method_a(self) -> None: ...
    async def method_b(self, val: zdc.u32) -> None: ...


@zdc.dataclass
class MultiMethodImpl(zdc.Component):
    """Implementation with multiple methods."""
    _a_count: int = zdc.field(default=0)
    _b_sum: int = zdc.field(default=0)
    
    async def method_a(self) -> None:
        self._a_count += 1
    
    async def method_b(self, val: zdc.u32) -> None:
        self._b_sum += val


@zdc.dataclass
class MultiMethodExportTuple(zdc.Component):
    """Component with tuple of exports having multiple methods."""
    api: Tuple[IMultiMethod, ...] = zdc.tuple(size=3, elem_factory=zdc.export)
    impls: Tuple[MultiMethodImpl, ...] = zdc.tuple(size=3, elem_factory=MultiMethodImpl)
    
    def __bind__(self):
        ret = []
        for i in range(3):
            # Bind both methods for each element
            ret.append((
                self.api[i].method_a,
                cast(MultiMethodImpl, self.impls[i]).method_a
            ))
            ret.append((
                self.api[i].method_b,
                cast(MultiMethodImpl, self.impls[i]).method_b
            ))
        return tuple(ret)


class TestMultiMethodTupleExport:
    """Test tuple exports with multiple methods per protocol."""
    
    def test_construction(self):
        """Test construction of component with multi-method tuple exports."""
        comp = MultiMethodExportTuple()
        assert len(comp.api) == 3
        assert len(comp.impls) == 3
    
    def test_call_through_multiple_methods(self):
        """Test that multiple methods can be called through exports."""
        async def _run():
            comp = MultiMethodExportTuple()
            
            # Call method_a on api[0], method_b on api[1]
            await comp.api[0].method_a()
            await comp.api[1].method_b(42)
            await comp.api[2].method_a()
            await comp.api[2].method_b(10)
            
            # Verify calls
            assert comp.impls[0]._a_count == 1
            assert comp.impls[0]._b_sum == 0
            assert comp.impls[1]._a_count == 0
            assert comp.impls[1]._b_sum == 42
            assert comp.impls[2]._a_count == 1
            assert comp.impls[2]._b_sum == 10
        
        asyncio.run(_run())


class TestTupleExportIR:
    """Test IR/datamodel generation for tuple exports."""
    
    def test_tuple_field_in_ir(self):
        """Test that tuple fields are properly represented in IR."""
        factory = zdc.DataModelFactory()
        ctx = factory.build([SimpleExportTuple])
        
        # Check that the type was processed
        assert 'SimpleExportTuple' in ctx.type_m
        comp_dt = ctx.type_m['SimpleExportTuple']
        
        # Find the req field
        req_field = next((f for f in comp_dt.fields if f.name == 'req'), None)
        assert req_field is not None, "Should have 'req' field"
        
        from zuspec.dataclasses.ir.data_type import DataTypeTuple
        assert isinstance(req_field.datatype, DataTypeTuple), "req should be DataTypeTuple"
        assert req_field.datatype.size == 2, "req size should be 2"
    
    def test_bind_map_with_subscript(self):
        """Test that bind_map captures subscript expressions for tuple elements."""
        factory = zdc.DataModelFactory()
        ctx = factory.build([SimpleExportTuple])
        
        comp_dt = ctx.type_m['SimpleExportTuple']
        
        # The bind_map should have entries for each element
        assert len(comp_dt.bind_map) == 2, f"Should have 2 bind entries, got {len(comp_dt.bind_map)}"
        
        # Each bind should reference subscripted fields
        for bind in comp_dt.bind_map:
            # LHS should reference req[i].req_transfer
            # RHS should reference channels[i].req_transfer
            assert bind.lhs is not None
            assert bind.rhs is not None
