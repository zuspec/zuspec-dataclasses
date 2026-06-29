"""Tests for Constraint System Builder"""

import pytest
from zuspec.ir.core.data_type import DataTypeInt, DataTypeStruct, Function
from zuspec.ir.core.fields import Field
from zuspec.ir.core.stmt import StmtExpr
from zuspec.ir.core.expr import ExprBin, ExprRefField, ExprConstant, BinOp, TypeExprRefSelf
from zuspec.be.py.solver.frontend import ConstraintSystemBuilder, BuildError
from zuspec.be.py.solver.core import Variable, IntDomain, CompareConstraint


class TestConstraintSystemBuilder:
    """Test constraint system builder"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.builder = ConstraintSystemBuilder()
    
    def test_build_simple_system(self):
        """Test building simple constraint system"""
        # Create variables
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        var_y = Variable("y", domain)
        
        # Create constraint expressions: x < y
        constraint_expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Lt,
            rhs=ExprRefLocal(name="y")
        )
        
        # Build system
        system = self.builder.build_simple([var_x, var_y], [constraint_expr])
        
        assert len(system.variables) == 2
        assert len(system.constraints) == 1
        assert "x" in system.variables
        assert "y" in system.variables
    
    def test_build_with_metadata(self):
        """Test building from struct with metadata"""
        # Create struct
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False)),
                Field(name="y", datatype=DataTypeInt(bits=8, signed=False))
            ],
            functions=[]
        )
        
        # Metadata
        metadata = {
            "x": {"rand": True, "rand_kind": "rand"},
            "y": {"rand": True, "rand_kind": "rand"}
        }
        
        # For now, we need to add a constraint function manually
        # In real IR, this would come from @constraint decorated method
        constraint_func = Function(
            name="valid_range",
            body=[
                StmtExpr(
                    expr=ExprBin(
                        lhs=ExprRefField(base=TypeExprRefSelf(), index=0),
                        op=BinOp.Lt,
                        rhs=ExprRefField(base=TypeExprRefSelf(), index=1)
                    )
                )
            ],
            metadata={"_is_constraint": True}
        )
        struct.functions.append(constraint_func)
        
        # Build system
        system = self.builder.build_from_struct(struct, metadata)
        
        assert len(system.variables) == 2
        assert len(system.constraints) == 1
    
    def test_build_no_variables_raises_error(self):
        """Test that building with no variables raises error"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False))
            ],
            functions=[]
        )
        
        # No metadata = no rand variables
        metadata = {}
        
        with pytest.raises(BuildError, match="No random variables"):
            self.builder.build_from_struct(struct, metadata)
    
    def test_build_no_constraints_raises_error(self):
        """Test that building with no constraints raises error"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False))
            ],
            functions=[]  # No constraint functions
        )
        
        # Update: We now allow systems with no constraints (just random var selection)
        # So this test is no longer valid - comment out
        # metadata = {"x": {"rand": True}}
        # with pytest.raises(BuildError, match="No constraints"):
        #     self.builder.build_from_struct(struct, metadata)
    
    @pytest.mark.skip(reason="No longer require constraints - unconstrained randomization is valid")
    def test_build_no_constraints_raises_error_old(self):
        """Old test: verify no constraints causes error - now skipped"""
        pass
    
    def test_add_ordering_constraint(self):
        """Test adding solve...before ordering"""
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        var_y = Variable("y", domain)
        
        constraint_expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Lt,
            rhs=ExprConstant(value=100)
        )
        
        system = self.builder.build_simple(
            [var_x, var_y],
            [constraint_expr],
            ordering_constraints=[("x", "y")]  # Solve x before y
        )
        
        assert var_x in var_y.order_constraints
    
    def test_add_ordering_circular_raises_error(self):
        """Test that circular ordering raises error"""
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        var_y = Variable("y", domain)
        
        constraint_expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Lt,
            rhs=ExprConstant(value=100)
        )
        
        # Create circular dependency: x before y, y before x
        with pytest.raises(BuildError, match="circular"):
            self.builder.build_simple(
                [var_x, var_y],
                [constraint_expr],
                ordering_constraints=[("x", "y"), ("y", "x")]
            )
    
    def test_add_ordering_unknown_variable_raises_error(self):
        """Test that ordering with unknown variable raises error"""
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        
        constraint_expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Lt,
            rhs=ExprConstant(value=100)
        )
        
        with pytest.raises(BuildError, match="Unknown variable"):
            self.builder.build_simple(
                [var_x],
                [constraint_expr],
                ordering_constraints=[("x", "unknown")]
            )
    
    def test_multiple_constraints(self):
        """Test building system with multiple constraints"""
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        var_y = Variable("y", domain)
        
        # x < 100 AND y > 10
        constraints = [
            ExprBin(
                lhs=ExprRefLocal(name="x"),
                op=BinOp.Lt,
                rhs=ExprConstant(value=100)
            ),
            ExprBin(
                lhs=ExprRefLocal(name="y"),
                op=BinOp.Gt,
                rhs=ExprConstant(value=10)
            )
        ]
        
        system = self.builder.build_simple([var_x, var_y], constraints)
        
        assert len(system.constraints) == 2
    
    def test_connected_components_computed(self):
        """Test that connected components are computed"""
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        var_y = Variable("y", domain)
        var_z = Variable("z", domain)
        
        # x < y (connects x and y)
        # z < 100 (z is independent)
        constraints = [
            ExprBin(
                lhs=ExprRefLocal(name="x"),
                op=BinOp.Lt,
                rhs=ExprRefLocal(name="y")
            ),
            ExprBin(
                lhs=ExprRefLocal(name="z"),
                op=BinOp.Lt,
                rhs=ExprConstant(value=100)
            )
        ]
        
        system = self.builder.build_simple([var_x, var_y, var_z], constraints)
        
        # Should have 2 connected components
        assert len(system.connected_components) == 2
    
    def test_get_constraint_source(self):
        """Test getting IR expression for constraint"""
        domain = IntDomain([(0, 255)], width=8, signed=False)
        var_x = Variable("x", domain)
        
        constraint_expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Lt,
            rhs=ExprConstant(value=100)
        )
        
        system = self.builder.build_simple([var_x], [constraint_expr])
        
        # Get the constraint
        constraint = system.constraints[0]
        
        # Should be able to get source
        source = self.builder.get_constraint_source(constraint)
        assert source == constraint_expr
    
    def test_constraint_function_detection(self):
        """Test that constraint functions are detected"""
        # This is tested indirectly through build_from_struct
        # but we can test the helper method
        func = Function(
            name="test",
            body=[],
            metadata={"_is_constraint": True}
        )
        
        assert self.builder._is_constraint_function(func)
    
    def test_invariant_function_detected(self):
        """Test that invariant functions are detected as constraints"""
        func = Function(
            name="test",
            body=[],
            is_invariant=True
        )
        
        assert self.builder._is_constraint_function(func)


# Need to import ExprRefLocal for tests
from zuspec.ir.core.expr import ExprRefLocal


# ---------------------------------------------------------------------------
# Tests for _extract_resource_id_vars and pool registration
# ---------------------------------------------------------------------------

import dataclasses as _dc
import zuspec.dataclasses as zdc
from zuspec.dataclasses.types import ClaimPool
from zuspec.be.py.rt.resource_rt import make_resource


@zdc.dataclass
class _GprComp(zdc.Component):
    gpr: ClaimPool = zdc.pool(
        default_factory=lambda: ClaimPool.fromList([10, 20, 30, 40])
    )


@zdc.dataclass
class _RsAction(zdc.Action[_GprComp]):
    rs1: zdc.Resource[zdc.u32] = zdc.share()
    output_val: zdc.u32 = zdc.rand()

    def __bind__(self):
        return (
            (self.rs1, self.comp.gpr),
        )

    @zdc.constraint
    def c_val(self):
        assert self.output_val == self.rs1.t


def _make_rs_action():
    comp = _GprComp()
    action = object.__new__(_RsAction)
    for f in _dc.fields(_RsAction):
        object.__setattr__(action, f.name, f.default if f.default is not _dc.MISSING else None)
    object.__setattr__(action, 'comp', comp)
    return action


class TestResourceIdVarExtraction:
    """Tests for _extract_resource_id_vars and pool registration in builder."""

    def test_extract_resource_id_vars_creates_id_variable(self):
        """_extract_resource_id_vars synthesises rs1.id with pool-size domain."""
        action = _make_rs_action()
        builder = ConstraintSystemBuilder()
        vars_ = builder._extract_resource_id_vars(action)
        names = [v.name for v in vars_]
        assert "rs1.id" in names

    def test_extract_resource_id_vars_domain_fits_pool(self):
        """Domain of rs1.id covers all pool slot indices."""
        action = _make_rs_action()
        builder = ConstraintSystemBuilder()
        vars_ = builder._extract_resource_id_vars(action)
        id_var = next(v for v in vars_ if v.name == "rs1.id")
        # pool has 4 elements; domain must include 0..3
        all_vals = list(id_var.domain.values())
        assert 0 in all_vals
        assert 3 in all_vals

    def test_extract_resource_id_vars_registers_pool(self):
        """Pool is registered in expr_parser.resource_pools after extraction."""
        action = _make_rs_action()
        builder = ConstraintSystemBuilder()
        builder._extract_resource_id_vars(action)
        assert "rs1" in builder.expr_parser.resource_pools
