"""Debugger integration for the PSS activity runner.

When a sys.settrace-based debugger (pdb, debugpy/VS Code, PyCharm) is active,
_fire_line_event() creates a real CPython frame at the user's source location
so the debugger fires a line event there.  No-op when no debugger is attached.

Example::

    >>> import sys
    >>> sys.gettrace() is None
    True
    >>> _fire_line_event("test.py", 10, {})  # no-op when no trace
"""
from __future__ import annotations

import ast
import sys
from typing import Any, Optional


def _fire_line_event(
    filename: str,
    lineno: int,
    local_vars: Optional[dict[str, Any]],
) -> None:
    """Fire a ``line`` trace event at *filename*:*lineno*.

    Creates a real CPython frame at the specified location by compiling and
    executing a bare ``pass`` AST node.  Any active ``sys.settrace`` debugger
    sees this as a genuine line event and will stop if a breakpoint is set there.

    Zero overhead when no debugger is attached (guarded by ``sys.gettrace()``).
    """
    if sys.gettrace() is None:
        return

    if not filename or lineno <= 0:
        return

    stmt = ast.Pass()
    stmt.lineno = lineno
    stmt.col_offset = 0
    stmt.end_lineno = lineno
    stmt.end_col_offset = 4
    mod = ast.Module(body=[stmt], type_ignores=[])
    ast.fix_missing_locations(mod)
    code = compile(mod, filename, "exec")
    exec(code, local_vars or {})  # noqa: S102
