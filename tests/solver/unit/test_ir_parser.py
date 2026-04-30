"""Tests for IR Expression Parser"""

import pytest
from zuspec.ir.core.expr import (
    ExprConstant, ExprBin, ExprUnary, ExprBool, ExprCompare,
    ExprRefLocal, ExprRefField, ExprRefBottomUp, ExprSubscript, ExprSlice,
    BinOp, UnaryOp, BoolOp, CmpOp, TypeExprRefSelf, ExprAttribute,
)
from zuspec.dataclasses.solver.frontend import IRExpressionParser, ParseError
from zuspec.dataclasses.solver.core import (
    Variable, IntDomain,
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    CompareConstraint, UnaryOpConstraint, BoolOpConstraint,
    CompareChainConstraint, BitSliceConstraint,
)
from zuspec.dataclasses.solver.core.constraints import ImplicationConstraint


class TestIRExpressionParser:
    """Test IR expression parser"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.parser = IRExpressionParser()
        
        # Create some test variables
        domain8 = IntDomain([(0, 255)], width=8, signed=False)
        domain16 = IntDomain([(0, 65535)], width=16, signed=False)
        
        self.var_x = Variable("x", domain8)
        self.var_y = Variable("y", domain8)
        self.var_z = Variable("z", domain16)
        
        # Register variables
        self.parser.register_variable("x", self.var_x)
        self.parser.register_variable("y", self.var_y)
        self.parser.register_variable("z", self.var_z)
        
        # Register field mappings
        self.parser.register_field(0, "x")
        self.parser.register_field(1, "y")
        self.parser.register_field(2, "z")
    
    def test_parse_constant(self):
        """Test parsing constant values"""
        expr = ExprConstant(value=42)
        result = self.parser.parse(expr)
        
        assert isinstance(result, ConstantConstraint)
        assert result.value == 42
    
    def test_parse_constant_non_int_raises_error(self):
        """Test that non-integer constants raise error"""
        expr = ExprConstant(value="hello")
        
        with pytest.raises(ParseError, match="Only integer constants"):
            self.parser.parse(expr)
    
    def test_parse_variable_ref_local(self):
        """Test parsing local variable reference"""
        expr = ExprRefLocal(name="x")
        result = self.parser.parse(expr)
        
        assert isinstance(result, VariableRefConstraint)
        assert result.variable == self.var_x
    
    def test_parse_variable_ref_field(self):
        """Test parsing field reference"""
        expr = ExprRefField(base=TypeExprRefSelf(), index=1)
        result = self.parser.parse(expr)
        
        assert isinstance(result, VariableRefConstraint)
        assert result.variable == self.var_y
    
    def test_parse_variable_ref_bottom_up(self):
        """Test parsing bottom-up field reference"""
        expr = ExprRefBottomUp()
        expr.index = 2
        expr.uplevel = 0
        result = self.parser.parse(expr)
        
        assert isinstance(result, VariableRefConstraint)
        assert result.variable == self.var_z
    
    def test_parse_unknown_variable_raises_error(self):
        """Test that unknown variable raises error"""
        expr = ExprRefLocal(name="unknown")
        
        with pytest.raises(ParseError, match="Unknown variable"):
            self.parser.parse(expr)
    
    def test_parse_binary_add(self):
        """Test parsing addition"""
        expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Add,
            rhs=ExprConstant(value=10)
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, BinaryOpConstraint)
        assert result.op == BinOp.Add
        assert isinstance(result.left, VariableRefConstraint)
        assert isinstance(result.right, ConstantConstraint)
    
    def test_parse_binary_comparison(self):
        """Test parsing comparison operation"""
        expr = ExprBin(
            lhs=ExprRefLocal(name="x"),
            op=BinOp.Lt,
            rhs=ExprConstant(value=100)
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, CompareConstraint)
        assert result.op == CmpOp.Lt
        assert isinstance(result.left, VariableRefConstraint)
        assert isinstance(result.right, ConstantConstraint)
    
    def test_parse_unary_negation(self):
        """Test parsing unary negation"""
        expr = ExprUnary(
            op=UnaryOp.USub,
            operand=ExprRefLocal(name="x")
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, UnaryOpConstraint)
        assert result.op == UnaryOp.USub
        assert isinstance(result.operand, VariableRefConstraint)
    
    def test_parse_unary_not(self):
        """Test parsing logical NOT"""
        expr = ExprUnary(
            op=UnaryOp.Not,
            operand=ExprRefLocal(name="x")
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, UnaryOpConstraint)
        assert result.op == UnaryOp.Not
    
    def test_parse_bool_and(self):
        """Test parsing boolean AND"""
        expr = ExprBool(
            op=BoolOp.And,
            values=[
                ExprRefLocal(name="x"),
                ExprRefLocal(name="y")
            ]
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, BoolOpConstraint)
        assert result.op == BoolOp.And
        assert len(result.values) == 2
    
    def test_parse_bool_or(self):
        """Test parsing boolean OR"""
        expr = ExprBool(
            op=BoolOp.Or,
            values=[
                ExprRefLocal(name="x"),
                ExprRefLocal(name="y"),
                ExprRefLocal(name="z")
            ]
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, BoolOpConstraint)
        assert result.op == BoolOp.Or
        assert len(result.values) == 3
    
    def test_parse_compare_single(self):
        """Test parsing single comparison"""
        expr = ExprCompare(
            left=ExprRefLocal(name="x"),
            ops=[CmpOp.Lt],
            comparators=[ExprConstant(value=100)]
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, CompareConstraint)
        assert result.op == CmpOp.Lt
    
    def test_parse_compare_chain(self):
        """Test parsing comparison chain"""
        expr = ExprCompare(
            left=ExprRefLocal(name="x"),
            ops=[CmpOp.Lt, CmpOp.Lt],
            comparators=[
                ExprRefLocal(name="y"),
                ExprRefLocal(name="z")
            ]
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, CompareChainConstraint)
        assert len(result.ops) == 2
        assert len(result.comparators) == 2
    
    def test_parse_bit_slice(self):
        """Test parsing bit slice"""
        expr = ExprSubscript(
            value=ExprRefLocal(name="z"),
            slice=ExprSlice(
                lower=ExprConstant(value=0),
                upper=ExprConstant(value=7),
                is_bit_slice=True
            )
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, BitSliceConstraint)
        assert result.variable == self.var_z
        assert result.lower == 0
        assert result.upper == 7
    
    def test_parse_bit_select(self):
        """Test parsing single bit select"""
        expr = ExprSubscript(
            value=ExprRefLocal(name="z"),
            slice=ExprConstant(value=3)
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, BitSliceConstraint)
        assert result.variable == self.var_z
        assert result.lower == 3
        assert result.upper == 3
    
    def test_parse_nested_expression(self):
        """Test parsing nested expression"""
        # (x + 10) < y
        expr = ExprBin(
            lhs=ExprBin(
                lhs=ExprRefLocal(name="x"),
                op=BinOp.Add,
                rhs=ExprConstant(value=10)
            ),
            op=BinOp.Lt,
            rhs=ExprRefLocal(name="y")
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, CompareConstraint)
        assert isinstance(result.left, BinaryOpConstraint)
        assert isinstance(result.right, VariableRefConstraint)
    
    def test_parse_complex_boolean(self):
        """Test parsing complex boolean expression"""
        # (x < 10) && (y > 5)
        expr = ExprBool(
            op=BoolOp.And,
            values=[
                ExprBin(
                    lhs=ExprRefLocal(name="x"),
                    op=BinOp.Lt,
                    rhs=ExprConstant(value=10)
                ),
                ExprBin(
                    lhs=ExprRefLocal(name="y"),
                    op=BinOp.Gt,
                    rhs=ExprConstant(value=5)
                )
            ]
        )
        result = self.parser.parse(expr)
        
        assert isinstance(result, BoolOpConstraint)
        assert result.op == BoolOp.And
        assert all(isinstance(v, CompareConstraint) for v in result.values)
    
    def test_variable_collection(self):
        """Test that variables are correctly collected"""
        # x + y < z
        expr = ExprBin(
            lhs=ExprBin(
                lhs=ExprRefLocal(name="x"),
                op=BinOp.Add,
                rhs=ExprRefLocal(name="y")
            ),
            op=BinOp.Lt,
            rhs=ExprRefLocal(name="z")
        )
        result = self.parser.parse(expr)
        
        # Check that all three variables are collected
        assert len(result.variables) == 3
        assert self.var_x in result.variables
        assert self.var_y in result.variables
        assert self.var_z in result.variables


# ---------------------------------------------------------------------------
# Resource pool ITE expansion tests (register_resource_pool / _build_pool_ite)
# ---------------------------------------------------------------------------

class _FakeResource:
    """Minimal resource stub that exposes a .t attribute."""
    def __init__(self, value):
        self._value = value

    @property
    def t(self):
        return self._value


class _FakePool:
    """Minimal pool stub with a .resources list."""
    def __init__(self, values):
        self.resources = [_FakeResource(v) for v in values]


class TestResourcePoolITE:
    """Tests for register_resource_pool / _build_pool_ite / _expand_pool_compare."""

    def setup_method(self):
        self.parser = IRExpressionParser()
        id_domain = IntDomain([(0, 3)], width=2, signed=False)
        self.id_var = Variable("rs1.id", id_domain)
        self.parser.register_variable("rs1.id", self.id_var)
        # field index 0 → "rs1" so ExprRefField(0) resolves to 'rs1'
        self.parser.register_field(0, "rs1")
        # field index 1 → "out_val" for LHS of comparisons
        out_domain = IntDomain([(0, 0xFFFFFFFF)], width=32, signed=False)
        self.out_var = Variable("out_val", out_domain)
        self.parser.register_variable("out_val", self.out_var)
        self.parser.register_field(1, "out_val")

    def _attr_expr(self):
        """Build ExprAttribute for self.rs1.t (ExprRefField(0).t)."""
        from zuspec.ir.core.expr import TypeExprRefSelf
        return ExprAttribute(value=ExprRefField(base=TypeExprRefSelf(), index=0), attr='t')

    def _compare_expr(self):
        """Build ExprCompare for self.out_val == self.rs1.t."""
        from zuspec.ir.core.expr import TypeExprRefSelf
        lhs = ExprRefField(base=TypeExprRefSelf(), index=1)
        rhs = ExprAttribute(value=ExprRefField(base=TypeExprRefSelf(), index=0), attr='t')
        return ExprCompare(left=lhs, ops=[CmpOp.Eq], comparators=[rhs])

    def test_register_resource_pool_adds_to_map(self):
        pool = _FakePool([10, 20, 30, 40])
        self.parser.register_resource_pool("rs1", pool)
        assert "rs1" in self.parser.resource_pools

    def test_build_pool_ite_returns_pool_value_ref(self):
        """_build_pool_ite returns a _PoolValueRef sentinel, not a Constraint."""
        from zuspec.dataclasses.solver.frontend.ir_parser import _PoolValueRef
        pool = _FakePool([10, 20, 30, 40])
        self.parser.register_resource_pool("rs1", pool)
        result = self.parser._build_pool_ite("rs1")
        assert isinstance(result, _PoolValueRef)
        assert result.values == [10, 20, 30, 40]
        assert result.id_var is self.id_var

    def test_parse_compare_resource_t_rhs_expands_to_and(self):
        """x == rs1.t over a 4-element pool → BoolOpConstraint(And, 4 implications)."""
        pool = _FakePool([10, 20, 30, 40])
        self.parser.register_resource_pool("rs1", pool)
        result = self.parser.parse(self._compare_expr())
        assert isinstance(result, BoolOpConstraint)
        assert result.op == BoolOp.And
        assert len(result.values) == 4

    def test_expand_pool_compare_implication_structure(self):
        """Each implication: if id==i then out_val==pool[i]."""
        pool = _FakePool([10, 20, 30, 40])
        self.parser.register_resource_pool("rs1", pool)
        result = self.parser.parse(self._compare_expr())
        for i, imp in enumerate(result.values):
            assert isinstance(imp, ImplicationConstraint)
            assert imp.else_constraint is None
            # condition: id == i
            cond = imp.condition
            assert isinstance(cond, CompareConstraint)
            assert isinstance(cond.right, ConstantConstraint)
            assert cond.right.value == i
            # then: out_val == pool[i]
            then = imp.then_constraint
            assert isinstance(then, CompareConstraint)
            assert isinstance(then.right, ConstantConstraint)
            assert then.right.value == [10, 20, 30, 40][i]

    def test_pool_ite_single_resource(self):
        """A one-element pool produces BoolOpConstraint(And, [single implication])."""
        pool = _FakePool([42])
        self.parser.register_resource_pool("rs1", pool)
        result = self.parser.parse(self._compare_expr())
        assert isinstance(result, BoolOpConstraint)
        assert len(result.values) == 1
        assert isinstance(result.values[0], ImplicationConstraint)

    def test_parse_resource_t_error_without_pool(self):
        """Parsing rs1.t without a registered pool raises ParseError."""
        with pytest.raises(ParseError, match="Unknown variable"):
            self.parser.parse(self._attr_expr())

    def test_parse_resource_t_error_without_id_var(self):
        """Parsing rs1.t without the id variable raises ParseError."""
        pool = _FakePool([1, 2])
        self.parser.register_resource_pool("rs1", pool)
        # Remove the id variable
        del self.parser.variable_map["rs1.id"]
        with pytest.raises(ParseError, match="No id variable"):
            self.parser.parse(self._compare_expr())


# ---------------------------------------------------------------------------
# match/case lowering tests
# ---------------------------------------------------------------------------

from zuspec.ir.core.stmt import (
    StmtMatch, StmtMatchCase, StmtAssert,
    PatternValue, PatternOr, PatternAs,
)
from zuspec.ir.core.expr import ExprRefLocal, ExprConstant, ExprCompare, CmpOp as IrCmpOp


class TestMatchCaseLowering:
    """Tests for _parse_match_statement — match/case → ImplicationConstraint."""

    def setup_method(self):
        self.parser = IRExpressionParser()
        domain8 = IntDomain([(0, 255)], width=8, signed=False)
        self.var_x = Variable("x", domain8)
        self.var_y = Variable("y", domain8)
        self.parser.register_variable("x", self.var_x)
        self.parser.register_variable("y", self.var_y)
        self.parser.register_field(0, "x")
        self.parser.register_field(1, "y")

    def _assert_stmt(self, expr):
        return StmtAssert(test=expr)

    def _eq(self, name, val):
        """Build ExprCompare: name == val."""
        return ExprCompare(
            left=ExprRefLocal(name=name),
            ops=[IrCmpOp.Eq],
            comparators=[ExprConstant(value=val)],
        )

    # ------------------------------------------------------------------
    # Simple PatternValue
    # ------------------------------------------------------------------

    def test_simple_pattern_value_produces_implication(self):
        """match x: case 1: assert y == 10  → (x==1) → (y==10)"""
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=1)),
                    body=[self._assert_stmt(self._eq("y", 10))],
                )
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 1
        impl = result[0]
        assert isinstance(impl, ImplicationConstraint)
        assert impl.else_constraint is None
        # condition: x == 1
        assert isinstance(impl.condition, CompareConstraint)
        assert impl.condition.op == CmpOp.Eq

    def test_two_cases_produce_two_implications(self):
        """Two case arms each produce one implication."""
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=1)),
                    body=[self._assert_stmt(self._eq("y", 10))],
                ),
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=2)),
                    body=[self._assert_stmt(self._eq("y", 20))],
                ),
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 2
        for impl in result:
            assert isinstance(impl, ImplicationConstraint)

    # ------------------------------------------------------------------
    # OR-pattern
    # ------------------------------------------------------------------

    def test_or_pattern_produces_disjunction_antecedent(self):
        """case 1 | 2: antecedent is BoolOpConstraint(Or, [x==1, x==2])."""
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternOr(patterns=[
                        PatternValue(value=ExprConstant(value=1)),
                        PatternValue(value=ExprConstant(value=2)),
                    ]),
                    body=[self._assert_stmt(self._eq("y", 99))],
                )
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 1
        impl = result[0]
        assert isinstance(impl.condition, BoolOpConstraint)
        assert impl.condition.op == BoolOp.Or
        assert len(impl.condition.values) == 2

    # ------------------------------------------------------------------
    # Wildcard case _
    # ------------------------------------------------------------------

    def test_wildcard_after_one_case_negates_prior(self):
        """case _: antecedent is NOT(x==1) when preceded by case 1."""
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=1)),
                    body=[self._assert_stmt(self._eq("y", 10))],
                ),
                StmtMatchCase(
                    pattern=PatternAs(pattern=None, name="_"),
                    body=[self._assert_stmt(self._eq("y", 0))],
                ),
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 2
        wildcard_impl = result[1]
        assert isinstance(wildcard_impl.condition, UnaryOpConstraint)
        assert wildcard_impl.condition.op == UnaryOp.Not

    def test_wildcard_with_no_prior_cases_is_tautology(self):
        """case _ with no prior cases → condition is ConstantConstraint(1)."""
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternAs(pattern=None, name="_"),
                    body=[self._assert_stmt(self._eq("y", 0))],
                ),
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 1
        assert isinstance(result[0].condition, ConstantConstraint)
        assert result[0].condition.value == 1

    # ------------------------------------------------------------------
    # Nested match
    # ------------------------------------------------------------------

    def test_nested_match_inherits_outer_antecedent(self):
        """Inner match arm's antecedent is AND(outer_cond, inner_cond)."""
        inner = StmtMatch(
            subject=ExprRefLocal(name="y"),
            cases=[
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=5)),
                    body=[self._assert_stmt(self._eq("x", 55))],
                )
            ],
        )
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=1)),
                    body=[inner],
                )
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 1
        impl = result[0]
        # antecedent is AND(x==1, y==5)
        assert isinstance(impl.condition, BoolOpConstraint)
        assert impl.condition.op == BoolOp.And
        assert len(impl.condition.values) == 2

    # ------------------------------------------------------------------
    # Guard (on a rand variable)
    # ------------------------------------------------------------------

    def test_guard_ands_with_pattern_condition(self):
        """case 1 if y == 0: antecedent is AND(x==1, y==0)."""
        stmt = StmtMatch(
            subject=ExprRefLocal(name="x"),
            cases=[
                StmtMatchCase(
                    pattern=PatternValue(value=ExprConstant(value=1)),
                    guard=self._eq("y", 0),
                    body=[self._assert_stmt(self._eq("y", 10))],
                )
            ],
        )
        result = self.parser.parse_statement(stmt)
        assert len(result) == 1
        impl = result[0]
        assert isinstance(impl.condition, BoolOpConstraint)
        assert impl.condition.op == BoolOp.And
        assert len(impl.condition.values) == 2


# ---------------------------------------------------------------------------
# Constraint-local witness variable tests
# ---------------------------------------------------------------------------

from zuspec.ir.core.stmt import StmtAnnAssign
from zuspec.ir.core.expr import ExprAttribute, ExprRefUnresolved, ExprCall
from zuspec.dataclasses.solver.core.variable import VarKind


class TestWitnessVariables:
    """Tests for constraint-local witness variable support (StmtAnnAssign)."""

    def setup_method(self):
        self.parser = IRExpressionParser()
        domain8 = IntDomain([(0, 255)], width=8, signed=False)
        self.var_x = Variable("x", domain8)
        self.parser.register_variable("x", self.var_x)
        self.parser.register_field(0, "x")

    def _zdc_rand_call(self):
        return ExprCall(
            func=ExprAttribute(
                value=ExprRefUnresolved(name="zdc"),
                attr="rand",
            ),
            args=[],
            keywords=[],
        )

    def _ann_assign(self, name, type_attr):
        return StmtAnnAssign(
            target=ExprRefUnresolved(name=name),
            annotation=ExprAttribute(
                value=ExprRefUnresolved(name="zdc"),
                attr=type_attr,
            ),
            value=self._zdc_rand_call(),
        )

    def test_witness_declaration_returns_no_constraints(self):
        """next_pc: zdc.u32 = zdc.rand() yields no constraints itself."""
        stmt = self._ann_assign("next_pc", "u32")
        result = self.parser.parse_statement(stmt)
        assert result == []

    def test_witness_registered_in_variable_map(self):
        """After declaration, the witness is accessible as a solver variable."""
        stmt = self._ann_assign("next_pc", "u32")
        self.parser.parse_statement(stmt)
        assert "next_pc" in self.parser.variable_map
        var = self.parser.variable_map["next_pc"]
        assert var.kind == VarKind.WITNESS

    def test_witness_u32_has_correct_domain(self):
        """zdc.u32 witness has domain [0, 0xFFFFFFFF] width=32 unsigned."""
        self.parser.parse_statement(self._ann_assign("w", "u32"))
        var = self.parser.variable_map["w"]
        assert var.domain.width == 32
        assert not var.domain.signed

    def test_witness_i8_has_correct_domain(self):
        """zdc.i8 witness has domain [-128, 127] width=8 signed."""
        self.parser.parse_statement(self._ann_assign("s", "i8"))
        var = self.parser.variable_map["s"]
        assert var.domain.width == 8
        assert var.domain.signed

    def test_witness_usable_in_subsequent_assert(self):
        """Witness declared then referenced in assert — resolves correctly."""
        from zuspec.ir.core.expr import ExprCompare, CmpOp as IrCmpOp
        # next_pc: zdc.u32 = zdc.rand()
        self.parser.parse_statement(self._ann_assign("next_pc", "u32"))
        # assert next_pc == 42
        assert_stmt = StmtAssert(
            test=ExprCompare(
                left=ExprRefLocal(name="next_pc"),
                ops=[IrCmpOp.Eq],
                comparators=[ExprConstant(value=42)],
            )
        )
        result = self.parser.parse_statement(assert_stmt)
        assert len(result) == 1
        assert isinstance(result[0], CompareConstraint)

    def test_non_rand_ann_assign_ignored(self):
        """AnnAssign without zdc.rand() RHS is silently ignored."""
        stmt = StmtAnnAssign(
            target=ExprRefUnresolved(name="foo"),
            annotation=ExprAttribute(value=ExprRefUnresolved(name="zdc"), attr="u8"),
            value=ExprConstant(value=0),
        )
        result = self.parser.parse_statement(stmt)
        assert result == []
        assert "foo" not in self.parser.variable_map
