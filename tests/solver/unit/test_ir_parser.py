"""Tests for IR Expression Parser"""

import pytest
from zuspec.ir.core.expr import (
    ExprConstant, ExprBin, ExprUnary, ExprBool, ExprCompare,
    ExprRefLocal, ExprRefField, ExprRefBottomUp, ExprSubscript, ExprSlice,
    BinOp, UnaryOp, BoolOp, CmpOp, TypeExprRefSelf
)
from zuspec.dataclasses.solver.frontend import IRExpressionParser, ParseError
from zuspec.dataclasses.solver.core import (
    Variable, IntDomain,
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    CompareConstraint, UnaryOpConstraint, BoolOpConstraint,
    CompareChainConstraint, BitSliceConstraint
)


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
