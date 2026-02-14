"""AST to IR Converter - converts Python AST to IR expressions.

This module provides conversion from Python AST nodes (from inline
constraints in randomize_with) to IR expression nodes for the solver.
"""

import ast
from typing import Any, Optional
from zuspec.dataclasses.ir.expr import (
    Expr, ExprConstant, ExprBin, ExprUnary, ExprCompare,
    ExprRefLocal, ExprAttribute, ExprCall, ExprSubscript,
    BinOp, UnaryOp, CmpOp
)
from zuspec.dataclasses.ir.data_type import DataTypeStruct


class ConversionError(Exception):
    """Exception raised when AST conversion fails"""
    pass


class AstToIrConverter:
    """Converts Python AST nodes to IR expressions.
    
    This is used to convert inline constraints specified in
    randomize_with() context managers to IR expressions that
    the solver can process.
    """
    
    def __init__(self, struct_type: DataTypeStruct):
        """Initialize converter.
        
        Args:
            struct_type: IR struct type for resolving field references
        """
        self.struct_type = struct_type
        self.field_names = {field.name for field in struct_type.fields}
    
    def convert_expr(self, node: ast.AST) -> Expr:
        """Convert an AST node to an IR expression.
        
        Args:
            node: Python AST node
            
        Returns:
            IR Expr node
            
        Raises:
            ConversionError: If node cannot be converted
        """
        if isinstance(node, ast.Constant):
            return self._convert_constant(node)
        
        elif isinstance(node, ast.Name):
            return self._convert_name(node)
        
        elif isinstance(node, ast.Attribute):
            return self._convert_attribute(node)
        
        elif isinstance(node, ast.BinOp):
            return self._convert_binop(node)
        
        elif isinstance(node, ast.UnaryOp):
            return self._convert_unaryop(node)
        
        elif isinstance(node, ast.Compare):
            return self._convert_compare(node)
        
        elif isinstance(node, ast.Call):
            return self._convert_call(node)
        
        elif isinstance(node, ast.Subscript):
            return self._convert_subscript(node)
        
        else:
            raise ConversionError(
                f"Unsupported AST node type: {node.__class__.__name__}"
            )
    
    def _convert_constant(self, node: ast.Constant) -> ExprConstant:
        """Convert constant value."""
        if isinstance(node.value, (int, bool)):
            return ExprConstant(value=int(node.value))
        else:
            raise ConversionError(
                f"Unsupported constant type: {type(node.value).__name__}"
            )
    
    def _convert_name(self, node: ast.Name) -> ExprRefLocal:
        """Convert variable name reference."""
        # Treat as a local variable reference
        return ExprRefLocal(name=node.id)
    
    def _convert_attribute(self, node: ast.Attribute) -> Expr:
        """Convert attribute access (e.g., self.addr, pkt.data)."""
        # Check if this is self.field or obj.field
        if isinstance(node.value, ast.Name):
            obj_name = node.value.id
            field_name = node.attr
            
            # Check if field exists in struct
            if field_name in self.field_names:
                # This is a field reference - create ExprRefLocal for the field
                return ExprRefLocal(name=field_name)
            else:
                # This might be a method call or nested field
                # For now, create ExprAttribute for method calls like .implies()
                value_ir = self.convert_expr(node.value)
                return ExprAttribute(value=value_ir, attr=field_name)
        
        # Nested attribute access
        value_ir = self.convert_expr(node.value)
        return ExprAttribute(value=value_ir, attr=node.attr)
    
    def _convert_binop(self, node: ast.BinOp) -> ExprBin:
        """Convert binary operation."""
        left = self.convert_expr(node.left)
        right = self.convert_expr(node.right)
        
        # Map Python AST op to IR BinOp
        op_map = {
            ast.Add: BinOp.Add,
            ast.Sub: BinOp.Sub,
            ast.Mult: BinOp.Mult,
            ast.Div: BinOp.Div,
            ast.FloorDiv: BinOp.Div,  # Treat as Div for integers
            ast.Mod: BinOp.Mod,
            ast.Pow: BinOp.Exp,  # Exp, not Pow
            ast.LShift: BinOp.LShift,
            ast.RShift: BinOp.RShift,
            ast.BitOr: BinOp.BitOr,
            ast.BitXor: BinOp.BitXor,
            ast.BitAnd: BinOp.BitAnd,
        }
        
        op_type = type(node.op)
        if op_type not in op_map:
            raise ConversionError(
                f"Unsupported binary operator: {node.op.__class__.__name__}"
            )
        
        return ExprBin(op=op_map[op_type], lhs=left, rhs=right)
    
    def _convert_unaryop(self, node: ast.UnaryOp) -> ExprUnary:
        """Convert unary operation."""
        operand = self.convert_expr(node.operand)
        
        # Map Python AST op to IR UnaryOp
        op_map = {
            ast.Not: UnaryOp.LogNot,
            ast.USub: UnaryOp.Neg,
            ast.Invert: UnaryOp.BitNot,
        }
        
        op_type = type(node.op)
        if op_type not in op_map:
            raise ConversionError(
                f"Unsupported unary operator: {node.op.__class__.__name__}"
            )
        
        return ExprUnary(op=op_map[op_type], expr=operand)
    
    def _convert_compare(self, node: ast.Compare) -> Expr:
        """Convert comparison operation.
        
        Python allows chained comparisons like a < b < c.
        For now, we handle simple two-operand comparisons.
        """
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ConversionError(
                "Chained comparisons not yet supported. "
                "Use 'and' to combine: (a < b) and (b < c)"
            )
        
        left = self.convert_expr(node.left)
        right = self.convert_expr(node.comparators[0])
        
        # Map Python AST comparison to IR CmpOp
        op_map = {
            ast.Eq: CmpOp.Eq,
            ast.NotEq: CmpOp.NotEq,
            ast.Lt: CmpOp.Lt,
            ast.LtE: CmpOp.LtE,
            ast.Gt: CmpOp.Gt,
            ast.GtE: CmpOp.GtE,
        }
        
        op_type = type(node.ops[0])
        if op_type not in op_map:
            raise ConversionError(
                f"Unsupported comparison operator: {node.ops[0].__class__.__name__}"
            )
        
        # Create ExprCompare with list structure matching Python AST
        return ExprCompare(
            left=left,
            ops=[op_map[op_type]],
            comparators=[right]
        )
    
    def _convert_call(self, node: ast.Call) -> ExprCall:
        """Convert function/method call."""
        # Convert function/method
        func_ir = self.convert_expr(node.func)
        
        # Convert arguments
        args_ir = [self.convert_expr(arg) for arg in node.args]
        
        # TODO: Handle keyword arguments if needed
        if node.keywords:
            raise ConversionError("Keyword arguments not yet supported")
        
        return ExprCall(func=func_ir, args=args_ir)
    
    def _convert_subscript(self, node: ast.Subscript) -> ExprSubscript:
        """Convert subscript expression (array indexing)."""
        # Convert base (what is being indexed)
        value_ir = self.convert_expr(node.value)
        
        # Convert index/slice
        slice_ir = self.convert_expr(node.slice)
        
        return ExprSubscript(value=value_ir, slice=slice_ir)


__all__ = ['AstToIrConverter', 'ConversionError']
