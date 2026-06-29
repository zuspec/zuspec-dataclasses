"""IRCompiler fast-path coverage (Phase 5 B1).

Builds small IR statement lists by hand, compiles them, and runs the result on a
plain object, asserting the compiled output matches PSS / interpreter semantics.
"""
from zuspec.ir.core.expr import (
    ExprConstant, ExprAttribute, TypeExprRefSelf, ExprCall, ExprRefLocal,
    ExprBin, ExprBool, BinOp, BoolOp, AugOp,
)
from zuspec.ir.core.stmt import (
    StmtAssign, StmtAnnAssign, StmtAugAssign, StmtFor, StmtWhile, StmtIf,
    StmtBreak, StmtExpr,
)

from zuspec.be.py.rt.ir_compiler import IRCompiler


class _Obj:
    pass


def _const(v):
    return ExprConstant(value=v)


def _self(attr):
    return ExprAttribute(value=TypeExprRefSelf(), attr=attr)


def _local(name):
    return ExprRefLocal(name=name)


def _assign_self(attr, value):
    return StmtAssign(targets=[_self(attr)], value=value)


def _run(stmts, **import_names):
    fn = IRCompiler().compile(stmts, **import_names)
    assert fn is not None, "expected the statements to compile"
    obj = _Obj()
    fn(obj)
    return obj


def test_pss_division_is_integer():
    # self.x = 7 / 2  ->  3  (PSS '/' is integer division)
    obj = _run([_assign_self("x", ExprBin(lhs=_const(7), op=BinOp.Div, rhs=_const(2)))])
    assert obj.x == 3


def test_for_loop_with_aug_assign():
    # total = 0; repeat (i : 4) { total += i }; self.s = total   -> 6
    stmts = [
        StmtAnnAssign(target=_local("total"), annotation=None, value=_const(0)),
        StmtFor(target=_local("i"), iter=_const(4), body=[
            StmtAugAssign(target=_local("total"), op=AugOp.Add, value=_local("i")),
        ], orelse=[]),
        _assign_self("s", _local("total")),
    ]
    assert _run(stmts).s == 6


def test_while_loop_with_break():
    # n = 0; while True { n += 1; if n >= 3 { break } }; self.n = n  -> 3
    stmts = [
        StmtAnnAssign(target=_local("n"), annotation=None, value=_const(0)),
        StmtWhile(test=_const(True), body=[
            StmtAugAssign(target=_local("n"), op=AugOp.Add, value=_const(1)),
            StmtIf(test=ExprBin(lhs=_local("n"), op=BinOp.GtE, rhs=_const(3)),
                   body=[StmtBreak()], orelse=[]),
        ], orelse=[]),
        _assign_self("n", _local("n")),
    ]
    assert _run(stmts).n == 3


def test_bool_and_or():
    obj = _run([
        _assign_self("a", ExprBool(op=BoolOp.And, values=[_const(True), _const(False)])),
        _assign_self("o", ExprBool(op=BoolOp.Or, values=[_const(False), _const(7)])),
    ])
    assert obj.a is False
    assert obj.o == 7


def test_print_builtin_uses_runtime_impl(capsys):
    # self.print("hi\n")  ->  routed to the PSS print (printf semantics)
    stmts = [StmtExpr(expr=ExprCall(func=_self("print"), args=[_const("hi\\n")]))]
    _run(stmts)
    assert capsys.readouterr().out == "hi\n"


def test_severity_constant_inlines():
    # self.v = LOW  ->  2  (std_pkg message_verbosity_e)
    obj = _run([_assign_self("v", _self("LOW"))])
    assert obj.v == 2


def test_import_call_bails_to_interpreter():
    # self.doit(1) with doit declared an import -> not compilable (None)
    stmts = [StmtExpr(expr=ExprCall(func=_self("doit"), args=[_const(1)]))]
    assert IRCompiler().compile(stmts, import_names={"doit"}) is None
