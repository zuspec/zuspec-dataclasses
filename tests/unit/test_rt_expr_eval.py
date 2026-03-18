"""Tests for rt/expr_eval.py — Phase 3."""
import pytest
from zuspec.dataclasses.rt.expr_eval import ExprEval
from zuspec.dataclasses.rt.action_context import ActionContext
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**fields):
    """Create a minimal ActionContext with a simple action namespace."""
    action = MagicMock()
    for name, value in fields.items():
        setattr(action, name, value)
    ctx = MagicMock(spec=ActionContext)
    ctx.action = action
    return ctx


def _eval(expr, **fields):
    return ExprEval(_ctx(**fields)).eval(expr)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_constant_int():
    assert _eval({'type': 'constant', 'value': 42}) == 42


def test_constant_bool():
    assert _eval({'type': 'constant', 'value': True}) is True


def test_constant_none():
    assert _eval({'type': 'constant', 'value': None}) is None


def test_constant_string():
    assert _eval({'type': 'constant', 'value': "hello"}) == "hello"


# ---------------------------------------------------------------------------
# Names and attributes
# ---------------------------------------------------------------------------

def test_name_self():
    ctx = _ctx(x=5)
    result = ExprEval(ctx).eval({'type': 'name', 'id': 'self'})
    assert result is ctx.action


def test_name_field():
    assert _eval({'type': 'name', 'id': 'count'}, count=7) == 7


def test_attribute_self_field():
    expr = {
        'type': 'attribute',
        'value': {'type': 'name', 'id': 'self'},
        'attr': 'count'
    }
    assert _eval(expr, count=10) == 10


def test_attribute_nested():
    class Inner:
        x = 99
    expr = {
        'type': 'attribute',
        'value': {
            'type': 'attribute',
            'value': {'type': 'name', 'id': 'self'},
            'attr': 'inner'
        },
        'attr': 'x'
    }
    inner = Inner()
    assert _eval(expr, inner=inner) == 99


# ---------------------------------------------------------------------------
# Binary operations
# ---------------------------------------------------------------------------

def test_bin_op_add():
    assert _eval({'type': 'bin_op', 'op': '+',
                  'left': {'type': 'constant', 'value': 3},
                  'right': {'type': 'constant', 'value': 4}}) == 7


def test_bin_op_sub():
    assert _eval({'type': 'bin_op', 'op': '-',
                  'left': {'type': 'constant', 'value': 10},
                  'right': {'type': 'constant', 'value': 3}}) == 7


def test_bin_op_mul():
    assert _eval({'type': 'bin_op', 'op': '*',
                  'left': {'type': 'constant', 'value': 6},
                  'right': {'type': 'constant', 'value': 7}}) == 42


def test_bin_op_floordiv():
    assert _eval({'type': 'bin_op', 'op': '//',
                  'left': {'type': 'constant', 'value': 10},
                  'right': {'type': 'constant', 'value': 3}}) == 3


def test_bin_op_mod():
    assert _eval({'type': 'bin_op', 'op': '%',
                  'left': {'type': 'constant', 'value': 10},
                  'right': {'type': 'constant', 'value': 3}}) == 1


def test_bin_op_bitwise():
    assert _eval({'type': 'bin_op', 'op': '&',
                  'left': {'type': 'constant', 'value': 0b1100},
                  'right': {'type': 'constant', 'value': 0b1010}}) == 0b1000


# ---------------------------------------------------------------------------
# Compare operations
# ---------------------------------------------------------------------------

def test_compare_lt():
    expr = {'type': 'compare', 'left': {'type': 'constant', 'value': 3},
            'ops': ['<'], 'comparators': [{'type': 'constant', 'value': 5}]}
    assert _eval(expr) is True


def test_compare_eq():
    expr = {'type': 'compare', 'left': {'type': 'constant', 'value': 5},
            'ops': ['=='], 'comparators': [{'type': 'constant', 'value': 5}]}
    assert _eval(expr) is True


def test_compare_neq():
    expr = {'type': 'compare', 'left': {'type': 'constant', 'value': 3},
            'ops': ['!='], 'comparators': [{'type': 'constant', 'value': 5}]}
    assert _eval(expr) is True


def test_compare_chained():
    """1 < 3 < 5 should be True."""
    expr = {'type': 'compare',
            'left': {'type': 'constant', 'value': 1},
            'ops': ['<', '<'],
            'comparators': [{'type': 'constant', 'value': 3},
                            {'type': 'constant', 'value': 5}]}
    assert _eval(expr) is True


def test_compare_field():
    expr = {
        'type': 'compare',
        'left': {'type': 'attribute', 'value': {'type': 'name', 'id': 'self'}, 'attr': 'n'},
        'ops': ['>'],
        'comparators': [{'type': 'constant', 'value': 0}]
    }
    assert _eval(expr, n=5) is True
    assert _eval(expr, n=-1) is False


# ---------------------------------------------------------------------------
# Boolean operations
# ---------------------------------------------------------------------------

def test_bool_and_true():
    expr = {'type': 'bool_op', 'op': 'and',
            'values': [{'type': 'constant', 'value': True},
                       {'type': 'constant', 'value': True}]}
    assert _eval(expr) is True


def test_bool_and_false():
    expr = {'type': 'bool_op', 'op': 'and',
            'values': [{'type': 'constant', 'value': True},
                       {'type': 'constant', 'value': False}]}
    assert _eval(expr) is False


def test_bool_or_true():
    expr = {'type': 'bool_op', 'op': 'or',
            'values': [{'type': 'constant', 'value': False},
                       {'type': 'constant', 'value': True}]}
    assert _eval(expr) is True


# ---------------------------------------------------------------------------
# Unary operations
# ---------------------------------------------------------------------------

def test_unary_not():
    assert _eval({'type': 'unary_op', 'op': 'not',
                  'operand': {'type': 'constant', 'value': False}}) is True


def test_unary_neg():
    assert _eval({'type': 'unary_op', 'op': '-',
                  'operand': {'type': 'constant', 'value': 5}}) == -5


# ---------------------------------------------------------------------------
# Subscript / list
# ---------------------------------------------------------------------------

def test_subscript_index():
    expr = {
        'type': 'subscript',
        'value': {'type': 'attribute', 'value': {'type': 'name', 'id': 'self'}, 'attr': 'items'},
        'slice': {'type': 'index', 'value': {'type': 'constant', 'value': 1}}
    }
    assert _eval(expr, items=[10, 20, 30]) == 20


def test_list_literal():
    expr = {'type': 'list', 'elts': [
        {'type': 'constant', 'value': 1},
        {'type': 'constant', 'value': 2},
        {'type': 'constant', 'value': 3},
    ]}
    assert _eval(expr) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Range
# ---------------------------------------------------------------------------

def test_range_stop_only():
    expr = {'type': 'range',
            'start': {'type': 'constant', 'value': 0},
            'stop': {'type': 'constant', 'value': 3},
            'step': {'type': 'constant', 'value': 1}}
    result = _eval(expr)
    assert list(result) == [0, 1, 2]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_unknown_type_raises():
    with pytest.raises(RuntimeError, match="unhandled expression type"):
        _eval({'type': 'unknown_thing'})


def test_unknown_bin_op_raises():
    with pytest.raises(RuntimeError, match="unknown binary op"):
        _eval({'type': 'bin_op', 'op': '@',
               'left': {'type': 'constant', 'value': 1},
               'right': {'type': 'constant', 'value': 2}})
