"""Compile PSS IR statement/expression trees to native Python callables.

This is a fast-path alternative to ``ObjectExecutor``.  For IR functions whose
bodies use only the subset of statements and expressions that appear in
``exec init_down`` and ``solve function`` blocks, we generate a Python source
string and compile it to real bytecode.  This avoids per-statement
``isinstance`` dispatch and recursive ``evaluate_expr`` calls.

Falls back gracefully: any statement type we can't handle is left for the
generic executor to run.  If any unhandled node is encountered during
compilation, the whole function falls back to ``ObjectExecutor``.
"""
from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------------------- #
# PSS builtin method name mapping                                              #
# --------------------------------------------------------------------------- #
_PSS_METHODS = {
    'push_back': 'append',
    'pop_back':  'pop',
    'size':      '__len__',  # special-cased in call handling
    'clear':     'clear',
    'delete':    'remove',
    'empty':     lambda base: f'(not {base})',
}

_BINOP_STR = {
    # NB: PSS '/' (BinOp.Div=4) is *integer* division — matches the interpreter's
    # ``left // right``.  FloorDiv=6 is also '//'.
    1: '+', 2: '-', 3: '*', 4: '//', 5: '%', 6: '//', 7: '**',
    8: '&', 9: '|', 10: '^', 11: '<<', 12: '>>',
    # Comparison ops embedded in BinOp
    13: '==', 14: '!=', 15: '<', 16: '<=', 17: '>', 18: '>=',
    19: 'and', 20: 'or',
}

# AugOp -> Python augmented-assignment operator.  Div=4 is integer division
# (matches the interpreter's ``a // b``).
_AUGOP_STR = {
    1: '+=', 2: '-=', 3: '*=', 4: '//=', 5: '%=', 6: '**=',
    7: '<<=', 8: '>>=', 9: '&=', 10: '|=', 11: '^=', 12: '//=',
}

# PSS builtin call functions that must use the runtime's implementation (printf
# semantics, escape handling) rather than Python's same-named builtin.
_PSS_BUILTIN_CALLS = {'print', 'message'}


class _Unhandled(Exception):
    """Raised when an IR node cannot be compiled."""


class IRCompiler:
    """Translates a list of IR Stmt nodes to a Python callable.

    Usage::

        fn = IRCompiler().compile(stmts, self_arg='self_comp')
        # fn(self_comp) executes the PSS code
    """

    def compile(self, stmts: list, self_arg: str = 'self_comp',
                extra_args: str = '', import_names=None) -> Optional[callable]:
        """Return a Python callable, or None if compilation is not possible.

        *import_names*, when given, is the set of package-scope import names the
        model may call.  A body referencing one is left to the interpreter (which
        routes it through the run's import resolver), so this compiler bails on it.
        """
        self._import_names = set(import_names) if import_names else set()
        try:
            lines = self._stmts(stmts, indent=1)
        except _Unhandled:
            return None
        if not lines:
            lines = ['    pass']
        args = self_arg
        if extra_args:
            args = f'{self_arg}, {extra_args}'
        src = f'def _pss_fn({args}):\n' + '\n'.join(lines)
        # PSS builtins available to compiled code (printf semantics).
        from .executor import _pss_print, _pss_message
        ns: dict = {'_pss_print': _pss_print, '_pss_message': _pss_message}
        try:
            exec(compile(src, '<pss_compiled>', 'exec'), ns)  # noqa: S102
        except Exception:
            # Any malformed generation falls back to the interpreter rather than
            # raising — compilation is strictly a best-effort fast path.
            return None
        return ns['_pss_fn']

    # ------------------------------------------------------------------ #
    # Statement compilation                                                #
    # ------------------------------------------------------------------ #

    def _stmts(self, stmts: list, indent: int) -> list[str]:
        lines = []
        for s in stmts:
            lines.extend(self._stmt(s, indent))
        return lines

    def _stmt(self, stmt, indent: int) -> list[str]:
        from zuspec.ir.core.stmt import (
            StmtAssign, StmtExpr, StmtIf, StmtReturn,
            StmtAnnAssign, StmtFor, StmtWhile, StmtAugAssign,
            StmtBreak, StmtContinue, StmtPass,
        )
        from zuspec.ir.core.expr import ExprRefLocal
        pad = '    ' * indent

        if isinstance(stmt, StmtAssign):
            targets = ', '.join(self._expr(t) for t in stmt.targets)
            value = self._expr(stmt.value)
            return [f'{pad}{targets} = {value}']

        elif isinstance(stmt, StmtExpr):
            return [f'{pad}{self._expr(stmt.expr)}']

        elif isinstance(stmt, StmtIf):
            test = self._expr(stmt.test)
            lines = [f'{pad}if {test}:']
            body = self._stmts(stmt.body, indent + 1)
            lines.extend(body if body else [f'{pad}    pass'])
            if stmt.orelse:
                lines.append(f'{pad}else:')
                orelse = self._stmts(stmt.orelse, indent + 1)
                lines.extend(orelse if orelse else [f'{pad}    pass'])
            return lines

        elif isinstance(stmt, StmtReturn):
            if stmt.value is not None:
                return [f'{pad}return {self._expr(stmt.value)}']
            return [f'{pad}return']

        elif isinstance(stmt, StmtAnnAssign):
            if stmt.value is not None:
                return [f'{pad}{self._expr(stmt.target)} = {self._expr(stmt.value)}']
            return []

        elif isinstance(stmt, StmtAugAssign):
            op = _AUGOP_STR.get(stmt.op.value if hasattr(stmt.op, 'value') else int(stmt.op))
            if op is None:
                raise _Unhandled(f'AugOp {stmt.op}')
            return [f'{pad}{self._expr(stmt.target)} {op} {self._expr(stmt.value)}']

        elif isinstance(stmt, StmtFor):
            # PSS repeat(N) / repeat(i : N) -> for <name> in range(int(N)):
            it = self._expr(stmt.iter)
            name = stmt.target.name if isinstance(stmt.target, ExprRefLocal) else '_i'
            lines = [f'{pad}for {name} in range(int({it})):']
            body = self._stmts(stmt.body, indent + 1)
            lines.extend(body if body else [f'{pad}    pass'])
            return lines

        elif isinstance(stmt, StmtWhile):
            lines = [f'{pad}while {self._expr(stmt.test)}:']
            body = self._stmts(stmt.body, indent + 1)
            lines.extend(body if body else [f'{pad}    pass'])
            return lines

        elif isinstance(stmt, StmtBreak):
            return [f'{pad}break']

        elif isinstance(stmt, StmtContinue):
            return [f'{pad}continue']

        elif isinstance(stmt, StmtPass):
            return [f'{pad}pass']

        else:
            raise _Unhandled(type(stmt).__name__)

    # ------------------------------------------------------------------ #
    # Expression compilation                                               #
    # ------------------------------------------------------------------ #

    def _expr(self, expr) -> str:
        from zuspec.ir.core.expr import (
            TypeExprRefSelf, ExprAttribute, ExprSubscript,
            ExprConstant, ExprBin, ExprUnary, ExprCompare,
            ExprCall, ExprRefUnresolved, ExprRefLocal, ExprIfExp,
            ExprBool, BoolOp,
        )

        if isinstance(expr, TypeExprRefSelf):
            return 'self_comp'

        elif isinstance(expr, ExprAttribute):
            # `self.<CONST>` for a std_pkg severity constant -> inline its value.
            if isinstance(expr.value, TypeExprRefSelf):
                from .executor import _PSS_CONSTANTS
                if expr.attr in _PSS_CONSTANTS:
                    return repr(_PSS_CONSTANTS[expr.attr])
            base = self._expr(expr.value)
            return f'{base}.{expr.attr}'

        elif isinstance(expr, ExprBool):
            sep = ' and ' if expr.op == BoolOp.And else ' or '
            return '(' + sep.join(self._expr(v) for v in expr.values) + ')'

        elif isinstance(expr, ExprSubscript):
            base = self._expr(expr.value)
            idx = self._expr(expr.slice)
            return f'{base}[{idx}]'

        elif isinstance(expr, ExprConstant):
            return repr(expr.value)

        elif isinstance(expr, ExprBin):
            op_str = _BINOP_STR.get(expr.op.value if hasattr(expr.op, 'value') else int(expr.op))
            if op_str is None:
                raise _Unhandled(f'BinOp {expr.op}')
            lhs = self._expr(expr.lhs)
            rhs = self._expr(expr.rhs)
            # Logical operators need parentheses to preserve precedence
            if op_str in ('and', 'or'):
                return f'({lhs} {op_str} {rhs})'
            return f'({lhs} {op_str} {rhs})'

        elif isinstance(expr, ExprUnary):
            op_map = {'not': 'not ', '-': '-', '+': '+', '~': '~'}
            op_str = op_map.get(expr.op, str(expr.op))
            return f'({op_str}{self._expr(expr.operand)})'

        elif isinstance(expr, ExprCompare):
            parts = [self._expr(expr.lhs)]
            op_names = {1: '==', 2: '!=', 3: '<', 4: '<=', 5: '>', 6: '>='}
            for op, cmp in zip(expr.ops, expr.comparators):
                v = op.value if hasattr(op, 'value') else int(op)
                parts.append(op_names.get(v, '=='))
                parts.append(self._expr(cmp))
            return '(' + ' '.join(parts) + ')'

        elif isinstance(expr, ExprCall):
            # Check for PSS collection builtins on attribute access
            func = expr.func
            if isinstance(func, ExprAttribute):
                method = func.attr
                # A package-scope import call (`self.<import>(...)`) must run on
                # the interpreter path so it routes through the import resolver.
                if (getattr(self, '_import_names', None)
                        and method in self._import_names
                        and isinstance(func.value, TypeExprRefSelf)):
                    raise _Unhandled(f'import call {method}')
                # PSS builtins (`print`/`message`) -> runtime impl with printf
                # semantics, not Python's same-named builtin.
                if method in _PSS_BUILTIN_CALLS and isinstance(func.value, TypeExprRefSelf):
                    args_str = ', '.join(self._expr(a) for a in expr.args)
                    return f'_pss_{method}({args_str})'
                base = self._expr(func.value)
                if method == 'push_back' and expr.args:
                    arg = self._expr(expr.args[0])
                    return f'{base}.append({arg})'
                elif method == 'pop_back':
                    return f'{base}.pop()'
                elif method == 'size':
                    return f'len({base})'
                elif method == 'clear':
                    return f'{base}.clear()'
                elif method == 'empty':
                    return f'(not {base})'
                # Regular method call (e.g. init_valid_pads())
                args_str = ', '.join(self._expr(a) for a in expr.args)
                return f'{base}.{method}({args_str})'
            # Plain function call (unlikely in PSS init contexts)
            func_str = self._expr(func)
            args_str = ', '.join(self._expr(a) for a in expr.args)
            return f'{func_str}({args_str})'

        elif isinstance(expr, ExprRefUnresolved):
            return expr.name

        elif isinstance(expr, ExprRefLocal):
            return expr.name

        elif isinstance(expr, ExprIfExp):
            test = self._expr(expr.test)
            body = self._expr(expr.body)
            orelse = self._expr(expr.orelse)
            return f'({body} if {test} else {orelse})'

        else:
            raise _Unhandled(type(expr).__name__)
