"""Tests for bind-map datamodel extraction as described in intro.rst."""
import zuspec.dataclasses as zdc
import zuspec.dataclasses.ir as dm
from typing import Protocol


def test_port_export_bind():
    """Test bind map extraction for port-to-export connections.
    
    According to intro.rst:
    - port, export, input, and output references are captured as indexed expressions
    - For: def __bind__(self): return { i.t : c.t }
    - Results in expressions like: ExprRefField(ExprRefField(0, TypeExprRefSelf()), 0)
    """
    
    class DataIF(Protocol):
        async def call(self, req : int) -> int: ...
    
    @zdc.dataclass
    class MyProdC(zdc.Component):
        prod : DataIF = zdc.port()
    
    @zdc.dataclass  
    class MyConsC(zdc.Component):
        cons : DataIF = zdc.export()
    
    @zdc.dataclass
    class MyC(zdc.Component):
        p : MyProdC = zdc.field()
        c : MyConsC = zdc.field()
        
        def __bind__(self): return {
            self.p.prod : self.c.cons
        }
    
    dm_ctxt = zdc.DataModelFactory().build(MyC)
    
    myc_qualname = MyC.__qualname__
    assert myc_qualname in dm_ctxt.type_m, f"MyC should be in context"
    
    myc_dm = dm_ctxt.type_m[myc_qualname]
    assert isinstance(myc_dm, dm.DataTypeComponent), \
        f"MyC should be DataTypeComponent, got {type(myc_dm).__name__}"
    
    # Verify bind_map has one entry
    assert len(myc_dm.bind_map) == 1, \
        f"MyC should have 1 bind entry, got {len(myc_dm.bind_map)}"
    
    bind = myc_dm.bind_map[0]
    assert isinstance(bind, dm.Bind), f"Bind map entry should be Bind, got {type(bind)}"
    
    # Verify LHS: self.p.prod -> ExprRefField(ExprRefField(TypeExprRefSelf, index=0), index=0)
    lhs = bind.lhs
    assert isinstance(lhs, dm.ExprRefField), f"LHS should be ExprRefField, got {type(lhs)}"
    assert lhs.index == 0, f"LHS inner index should be 0 (prod), got {lhs.index}"
    
    lhs_base = lhs.base
    assert isinstance(lhs_base, dm.ExprRefField), f"LHS base should be ExprRefField, got {type(lhs_base)}"
    assert lhs_base.index == 0, f"LHS base index should be 0 (p), got {lhs_base.index}"
    assert isinstance(lhs_base.base, dm.TypeExprRefSelf), \
        f"LHS base base should be TypeExprRefSelf, got {type(lhs_base.base)}"
    
    # Verify RHS: self.c.cons -> ExprRefField(ExprRefField(TypeExprRefSelf, index=1), index=0)
    rhs = bind.rhs
    assert isinstance(rhs, dm.ExprRefField), f"RHS should be ExprRefField, got {type(rhs)}"
    assert rhs.index == 0, f"RHS inner index should be 0 (cons), got {rhs.index}"
    
    rhs_base = rhs.base
    assert isinstance(rhs_base, dm.ExprRefField), f"RHS base should be ExprRefField, got {type(rhs_base)}"
    assert rhs_base.index == 1, f"RHS base index should be 1 (c), got {rhs_base.index}"
    assert isinstance(rhs_base.base, dm.TypeExprRefSelf), \
        f"RHS base base should be TypeExprRefSelf, got {type(rhs_base.base)}"


def test_method_bind():
    """Test bind map extraction for export API method to method connections.
    
    According to intro.rst, the bind map also captures:
    - export API type method and method
    
    For: def __bind__(self): return { self.cons.call : self.target }
    """
    
    class DataIF(Protocol):
        async def call(self, req : int) -> int: ...
    
    @zdc.dataclass
    class MyConsC(zdc.Component):
        cons : DataIF = zdc.export()
        
        def __bind__(self): return {
            self.cons.call : self.target
        }
        
        async def target(self, req : int) -> int:
            return req + 2
    
    dm_ctxt = zdc.DataModelFactory().build(MyConsC)
    
    myconsc_qualname = MyConsC.__qualname__
    myconsc_dm = dm_ctxt.type_m[myconsc_qualname]
    
    # Verify bind_map has one entry
    assert len(myconsc_dm.bind_map) == 1, \
        f"MyConsC should have 1 bind entry, got {len(myconsc_dm.bind_map)}"
    
    bind = myconsc_dm.bind_map[0]
    
    # LHS: self.cons.call -> ExprRefPy(ExprRefField(TypeExprRefSelf, 0), "call")
    lhs = bind.lhs
    assert isinstance(lhs, dm.ExprRefPy), f"LHS should be ExprRefPy, got {type(lhs)}"
    assert lhs.ref == "call", f"LHS ref should be 'call', got {lhs.ref}"
    
    lhs_base = lhs.base
    assert isinstance(lhs_base, dm.ExprRefField), \
        f"LHS base should be ExprRefField, got {type(lhs_base)}"
    assert lhs_base.index == 0, f"LHS base index should be 0 (cons), got {lhs_base.index}"
    
    # RHS: self.target -> ExprRefPy(TypeExprRefSelf, "target")
    rhs = bind.rhs
    assert isinstance(rhs, dm.ExprRefPy), f"RHS should be ExprRefPy, got {type(rhs)}"
    assert rhs.ref == "target", f"RHS ref should be 'target', got {rhs.ref}"
    assert isinstance(rhs.base, dm.TypeExprRefSelf), \
        f"RHS base should be TypeExprRefSelf, got {type(rhs.base)}"


def test_multiple_binds():
    """Test bind map extraction with multiple bind entries."""
    
    class IF1(Protocol):
        async def api1(self): ...
    
    class IF2(Protocol):
        async def api2(self): ...
    
    @zdc.dataclass
    class Prod(zdc.Component):
        p1 : IF1 = zdc.port()
        p2 : IF2 = zdc.port()
    
    @zdc.dataclass
    class Cons(zdc.Component):
        e1 : IF1 = zdc.export()
        e2 : IF2 = zdc.export()
    
    @zdc.dataclass
    class Top(zdc.Component):
        prod : Prod = zdc.field()
        cons : Cons = zdc.field()
        
        def __bind__(self): return {
            self.prod.p1 : self.cons.e1,
            self.prod.p2 : self.cons.e2
        }
    
    dm_ctxt = zdc.DataModelFactory().build(Top)
    
    top_dm = dm_ctxt.type_m[Top.__qualname__]
    
    # Should have 2 bind entries
    assert len(top_dm.bind_map) == 2, \
        f"Top should have 2 bind entries, got {len(top_dm.bind_map)}"
    
    # Verify both binds have correct structure
    for bind in top_dm.bind_map:
        assert isinstance(bind.lhs, dm.ExprRefField)
        assert isinstance(bind.rhs, dm.ExprRefField)


def test_no_bind_method():
    """Test that components without __bind__ have empty bind_map."""
    
    @zdc.dataclass
    class NoBind(zdc.Component):
        pass
    
    dm_ctxt = zdc.DataModelFactory().build(NoBind)
    
    nobind_dm = dm_ctxt.type_m[NoBind.__qualname__]
    assert len(nobind_dm.bind_map) == 0, \
        f"NoBind should have empty bind_map, got {len(nobind_dm.bind_map)}"


def test_bind_returns_none():
    """Test that components with __bind__ returning None have empty bind_map."""
    
    @zdc.dataclass
    class BindNone(zdc.Component):
        def __bind__(self): 
            return None
    
    dm_ctxt = zdc.DataModelFactory().build(BindNone)
    
    bindnone_dm = dm_ctxt.type_m[BindNone.__qualname__]
    assert len(bindnone_dm.bind_map) == 0, \
        f"BindNone should have empty bind_map, got {len(bindnone_dm.bind_map)}"


def test_inherited_bind_not_extracted():
    """Test that inherited __bind__ is not extracted for derived class."""
    
    class BaseIF(Protocol):
        async def api(self): ...
    
    @zdc.dataclass
    class BaseComp(zdc.Component):
        p : BaseIF = zdc.port()
        
        def __bind__(self): return {
            # This would need to reference something, but we're testing inheritance
        }
    
    @zdc.dataclass
    class DerivedComp(BaseComp):
        # No __bind__ defined here, inherits from BaseComp
        pass
    
    dm_ctxt = zdc.DataModelFactory().build(DerivedComp)
    
    derived_dm = dm_ctxt.type_m[DerivedComp.__qualname__]
    # Derived should have empty bind_map since it doesn't define __bind__ itself
    assert len(derived_dm.bind_map) == 0, \
        f"DerivedComp should have empty bind_map (inherited __bind__ not extracted)"


def test_nested_component_bind():
    """Test bind map extraction with deeply nested field access."""
    
    class IF(Protocol):
        async def call(self): ...
    
    @zdc.dataclass
    class Inner(zdc.Component):
        port_inner : IF = zdc.port()
    
    @zdc.dataclass
    class Middle(zdc.Component):
        inner : Inner = zdc.field()
    
    @zdc.dataclass
    class Export(zdc.Component):
        exp : IF = zdc.export()
    
    @zdc.dataclass
    class Outer(zdc.Component):
        mid : Middle = zdc.field()
        exp : Export = zdc.field()
        
        def __bind__(self): return {
            self.mid.inner.port_inner : self.exp.exp
        }
    
    dm_ctxt = zdc.DataModelFactory().build(Outer)
    
    outer_dm = dm_ctxt.type_m[Outer.__qualname__]
    assert len(outer_dm.bind_map) == 1
    
    bind = outer_dm.bind_map[0]
    
    # LHS: self.mid.inner.port_inner
    # Should be: ExprRefField(ExprRefField(ExprRefField(TypeExprRefSelf, 0), 0), 0)
    lhs = bind.lhs
    assert isinstance(lhs, dm.ExprRefField)
    assert lhs.index == 0  # port_inner
    
    lhs_inner = lhs.base
    assert isinstance(lhs_inner, dm.ExprRefField)
    assert lhs_inner.index == 0  # inner
    
    lhs_mid = lhs_inner.base
    assert isinstance(lhs_mid, dm.ExprRefField)
    assert lhs_mid.index == 0  # mid
    
    assert isinstance(lhs_mid.base, dm.TypeExprRefSelf)


def test_inherited_bind_augmented():
    """Test that derived class can augment base class __bind__ with local binds."""
    
    class IF1(Protocol):
        async def api1(self): ...
    
    class IF2(Protocol):
        async def api2(self): ...
    
    @zdc.dataclass
    class Prod(zdc.Component):
        p1 : IF1 = zdc.port()
        p2 : IF2 = zdc.port()
    
    @zdc.dataclass
    class Cons(zdc.Component):
        e1 : IF1 = zdc.export()
        e2 : IF2 = zdc.export()
    
    @zdc.dataclass
    class BaseTop(zdc.Component):
        prod : Prod = zdc.field()
        cons : Cons = zdc.field()
        
        def __bind__(self): return {
            self.prod.p1 : self.cons.e1
        }
    
    @zdc.dataclass
    class DerivedTop(BaseTop):
        """Derived class that augments base binds with additional local binds."""
        
        def __bind__(self): 
            # Get base class binds and augment with local binds
            base_binds = super().__bind__() or {}
            return {
                **base_binds,
                self.prod.p2 : self.cons.e2
            }
    
    dm_ctxt = zdc.DataModelFactory().build(DerivedTop)
    
    derived_dm = dm_ctxt.type_m[DerivedTop.__qualname__]
    
    # Should have 2 bind entries (1 from base + 1 local)
    assert len(derived_dm.bind_map) == 2, \
        f"DerivedTop should have 2 bind entries, got {len(derived_dm.bind_map)}"
    
    # Verify both binds have correct structure
    for bind in derived_dm.bind_map:
        assert isinstance(bind.lhs, dm.ExprRefField)
        assert isinstance(bind.rhs, dm.ExprRefField)
    
    # Check we have binds for both p1->e1 and p2->e2
    # prod is at index 0, cons is at index 1
    # p1/e1 are at index 0, p2/e2 are at index 1
    lhs_indices = set()
    rhs_indices = set()
    for bind in derived_dm.bind_map:
        lhs_indices.add(bind.lhs.index)
        rhs_indices.add(bind.rhs.index)
    
    assert lhs_indices == {0, 1}, f"Expected LHS indices {{0, 1}}, got {lhs_indices}"
    assert rhs_indices == {0, 1}, f"Expected RHS indices {{0, 1}}, got {rhs_indices}"
