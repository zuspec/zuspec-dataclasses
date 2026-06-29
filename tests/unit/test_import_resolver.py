"""Import-injection seam: resolver + executor routing + IRCompiler guard.

These tests drive the routing directly through ``ObjectExecutor`` with a
hand-built body IR, so they need neither a parser nor the ``zuspec.be.py``
builder — keeping the dependency direction clean.
"""
import pytest

from zuspec.ir.core.expr import ExprConstant, ExprAttribute, TypeExprRefSelf, ExprCall
from zuspec.ir.core.stmt import StmtExpr

from zuspec.be.py.rt.executor import ObjectExecutor
from zuspec.be.py.rt.import_resolver import (
    ImportResolver, ImportSpec, PssImportError, use_resolver, current_resolver,
)


def _self_call(name, *args):
    """IR for `self.<name>(<args>)` — how PSS lowers a package-scope import call."""
    return ExprCall(
        func=ExprAttribute(value=TypeExprRefSelf(), attr=name),
        args=list(args),
    )


def _const(v):
    return ExprConstant(value=v)


class _Obj:
    """Stand-in for an action instance (the ObjectExecutor target)."""


def _specs(*pairs):
    return {n: ImportSpec(name=n, is_target=t, is_solve=s) for (n, t, s) in pairs}


def test_nested_import_calls_route_to_impl():
    calls = []

    class Imp:
        def getval(self, i):
            calls.append(("getval", i))
            return i + 5

        def doit(self, i):
            calls.append(("doit", i))

    # body: doit(getval(7))
    body = [StmtExpr(expr=_self_call("doit", _self_call("getval", _const(7))))]
    resolver = ImportResolver(Imp(), _specs(("doit", True, False), ("getval", False, True)))

    with use_resolver(resolver):
        ObjectExecutor(_Obj()).execute_stmts(body)

    assert calls == [("getval", 7), ("doit", 12)]


def test_missing_import_raises_clear_error():
    class Imp:
        pass  # does not supply `doit`

    body = [StmtExpr(expr=_self_call("doit", _const(1)))]
    resolver = ImportResolver(Imp(), _specs(("doit", True, False)))

    with use_resolver(resolver):
        with pytest.raises(PssImportError, match="doit"):
            ObjectExecutor(_Obj()).execute_stmts(body)


def test_async_target_import_raises_clear_error():
    class Imp:
        async def doit(self, i):
            return None

    body = [StmtExpr(expr=_self_call("doit", _const(1)))]
    resolver = ImportResolver(Imp(), _specs(("doit", True, False)))

    with use_resolver(resolver):
        with pytest.raises(PssImportError, match="async"):
            ObjectExecutor(_Obj()).execute_stmts(body)


def test_no_resolver_falls_through_without_crashing():
    # With no resolver active, an unbound `self.foo()` evaluates to 0 (prior
    # behaviour) rather than raising.
    assert current_resolver() is None
    body = [StmtExpr(expr=_self_call("doit", _const(1)))]
    ObjectExecutor(_Obj()).execute_stmts(body)  # no exception


def test_unrelated_self_call_not_intercepted():
    # A real method on the object must still be called even when a resolver is
    # active, as long as the name is not a registered import.
    class Obj:
        def __init__(self):
            self.hit = None

        def helper(self, v):
            self.hit = v

    obj = Obj()
    body = [StmtExpr(expr=_self_call("helper", _const(9)))]
    resolver = ImportResolver(object(), _specs(("doit", True, False)))
    with use_resolver(resolver):
        ObjectExecutor(obj).execute_stmts(body)
    assert obj.hit == 9


def test_async_executor_awaits_async_import_target():
    import asyncio
    from zuspec.be.py.rt.executor import AsyncObjectExecutor

    seen = []

    class Imp:
        def getval(self, i):
            return i + 5

        async def doit(self, i):
            await asyncio.sleep(0)
            seen.append(i)

    body = [StmtExpr(expr=_self_call("doit", _self_call("getval", _const(7))))]
    resolver = ImportResolver(Imp(), _specs(("doit", True, False), ("getval", False, True)))

    async def go():
        with use_resolver(resolver):
            await AsyncObjectExecutor(_Obj()).execute_stmts_async(body)

    asyncio.run(go())
    assert seen == [12]      # async target awaited; sync solve arg resolved first


def test_async_executor_runs_sync_import_and_import_free_stmts():
    import asyncio
    from zuspec.be.py.rt.executor import AsyncObjectExecutor

    class Obj:
        def __init__(self):
            self.hit = None

        def helper(self, v):
            self.hit = v

    calls = []

    class Imp:
        def doit(self, i):          # synchronous import target
            calls.append(i)

    obj = Obj()
    # body: helper(3); doit(4)   — one import-free call, one sync import call
    body = [
        StmtExpr(expr=_self_call("helper", _const(3))),
        StmtExpr(expr=_self_call("doit", _const(4))),
    ]
    resolver = ImportResolver(Imp(), _specs(("doit", True, False)))

    async def go():
        with use_resolver(resolver):
            await AsyncObjectExecutor(obj).execute_stmts_async(body)

    asyncio.run(go())
    assert obj.hit == 3 and calls == [4]


def test_ircompiler_bails_on_import_call():
    from zuspec.be.py.rt.ir_compiler import IRCompiler

    body = [StmtExpr(expr=_self_call("getval", _const(7)))]
    # Without import_names, the compiler emits self_comp.getval(7) (a method call).
    assert IRCompiler().compile(body) is not None
    # With getval declared an import, it must bail so the interpreter routes it.
    assert IRCompiler().compile(body, import_names={"getval"}) is None
