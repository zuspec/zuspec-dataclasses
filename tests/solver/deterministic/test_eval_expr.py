"""Tests for EvalExpr IR nodes, EvalExprVisitor, ConstFold, and collect_vars."""
import pytest
from zuspec.ir.core.expr import BinOp, UnaryOp
from zuspec.dataclasses.solver.deterministic.eval_expr import (
    ExprConst, ExprVar, ExprBinOp, ExprUnary, ExprCbit,
    ExprSigned, ExprSext, ExprIf, ExprLookup, ExprMask,
    EvalExprVisitor, ConstFold, collect_vars,
)


# ---------------------------------------------------------------------------
# Basic node construction
# ---------------------------------------------------------------------------

def test_expr_const_value():
    e = ExprConst(42)
    assert e.value == 42


def test_expr_var_name():
    e = ExprVar("self.x")
    assert e.name == "self.x"


def test_expr_binop_fields():
    e = ExprBinOp(BinOp.Add, ExprConst(1), ExprConst(2))
    assert e.op == BinOp.Add
    assert isinstance(e.left, ExprConst)
    assert isinstance(e.right, ExprConst)


def test_expr_unary_fields():
    e = ExprUnary(UnaryOp.Invert, ExprConst(0xFF))
    assert e.op == UnaryOp.Invert
    assert isinstance(e.operand, ExprConst)


# ---------------------------------------------------------------------------
# ConstFold
# ---------------------------------------------------------------------------

def test_constfold_add():
    e = ExprBinOp(BinOp.Add, ExprConst(3), ExprConst(4))
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == 7


def test_constfold_sub():
    e = ExprBinOp(BinOp.Sub, ExprConst(10), ExprConst(3))
    result = ConstFold().visit(e)
    assert result.value == 7


def test_constfold_mul():
    e = ExprBinOp(BinOp.Mult, ExprConst(6), ExprConst(7))
    result = ConstFold().visit(e)
    assert result.value == 42


def test_constfold_bitand():
    e = ExprBinOp(BinOp.BitAnd, ExprConst(0xFF), ExprConst(0x0F))
    result = ConstFold().visit(e)
    assert result.value == 0x0F


def test_constfold_bitor():
    e = ExprBinOp(BinOp.BitOr, ExprConst(0xF0), ExprConst(0x0F))
    result = ConstFold().visit(e)
    assert result.value == 0xFF


def test_constfold_lshift():
    e = ExprBinOp(BinOp.LShift, ExprConst(1), ExprConst(4))
    result = ConstFold().visit(e)
    assert result.value == 16


def test_constfold_rshift():
    e = ExprBinOp(BinOp.RShift, ExprConst(32), ExprConst(2))
    result = ConstFold().visit(e)
    assert result.value == 8


def test_constfold_invert():
    e = ExprUnary(UnaryOp.Invert, ExprConst(0))
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == ~0


def test_constfold_usub():
    e = ExprUnary(UnaryOp.USub, ExprConst(5))
    result = ConstFold().visit(e)
    assert result.value == -5


def test_constfold_not():
    e = ExprUnary(UnaryOp.Not, ExprConst(0))
    result = ConstFold().visit(e)
    assert result.value != 0  # True-ish


def test_constfold_partial_var():
    """When there are free variables, only constant sub-expressions fold."""
    e = ExprBinOp(BinOp.Add, ExprVar("x"), ExprConst(0))
    result = ConstFold().visit(e)
    # 0 is identity for Add but ConstFold doesn't apply identity laws;
    # it just folds all-const nodes.  Result should still have ExprVar.
    assert any(isinstance(n, ExprVar) for n in [result.left if isinstance(result, ExprBinOp) else result])


def test_constfold_nested():
    inner = ExprBinOp(BinOp.Mult, ExprConst(2), ExprConst(3))
    outer = ExprBinOp(BinOp.Add, inner, ExprConst(10))
    result = ConstFold().visit(outer)
    assert isinstance(result, ExprConst)
    assert result.value == 16


def test_constfold_if_true():
    e = ExprIf(ExprConst(1), ExprConst(99), ExprConst(0))
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == 99


def test_constfold_if_false():
    e = ExprIf(ExprConst(0), ExprConst(99), ExprConst(7))
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == 7


def test_constfold_mask():
    e = ExprMask(ExprConst(0xABCD), 8)
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == 0xCD


# ---------------------------------------------------------------------------
# collect_vars
# ---------------------------------------------------------------------------

def test_collect_vars_empty():
    assert collect_vars(ExprConst(1)) == set()


def test_collect_vars_single():
    assert collect_vars(ExprVar("a")) == {"a"}


def test_collect_vars_deep():
    e = ExprBinOp(
        BinOp.Add,
        ExprVar("x"),
        ExprBinOp(BinOp.Sub, ExprVar("y"), ExprVar("x")),
    )
    assert collect_vars(e) == {"x", "y"}


def test_collect_vars_if():
    e = ExprIf(ExprVar("cond"), ExprVar("a"), ExprVar("b"))
    assert collect_vars(e) == {"cond", "a", "b"}


def test_collect_vars_lookup():
    e = ExprLookup("_TABLE", [ExprVar("k")], ExprConst(0))
    assert collect_vars(e) == {"k"}


# ---------------------------------------------------------------------------
# ExprSext folding
# ---------------------------------------------------------------------------

def test_constfold_sext_positive():
    # sext(0x7F, 8) == 127  (positive, no sign extension needed)
    e = ExprSext(ExprConst(0x7F), bits=8)
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == 127


def test_constfold_sext_negative():
    # sext(0xFF, 8) == -1
    e = ExprSext(ExprConst(0xFF), bits=8)
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == -1


def test_constfold_sext_minus128():
    # sext(0x80, 8) == -128
    e = ExprSext(ExprConst(0x80), bits=8)
    result = ConstFold().visit(e)
    assert isinstance(result, ExprConst)
    assert result.value == -128
