"""Pragma comment scanner for Zuspec DSL methods and class bodies.

Recognises ``# zdc: token, key=value, key="string"`` comments and returns a
line-number-keyed dict so the activity parser and field extractor can attach
pragma metadata to the corresponding IR nodes.

Syntax
------
A pragma comment starts with ``# zdc:`` (case-insensitive for the prefix,
but pragma names are lower-cased).  The body is a comma-separated list of
*items*::

    item := flag | key=value

``flag``      — boolean True shorthand; stored as ``{flag: True}``
``key=value`` — explicit value; *value* is parsed with
               ``ast.literal_eval`` so integers, floats, booleans and
               quoted strings all work.  Bare (unquoted) strings are
               kept as-is.

Examples::

    match self.cpu_state:  # zdc: parallel_case, full_case
    match self.alu_op:  # zdc: parallel_case
    await self.fetch()  # zdc: label=fetch_stage
    dbg_pc: zdc.bit32 = zdc.field()  # zdc: keep
    dbg_pc: zdc.bit32 = zdc.field()  # zdc: keep, label=debug_pc
    count: zdc.bit8 = zdc.field()  # zdc: rand_weight=10

Public API
----------
``scan_pragmas(source)`` → ``Dict[int, Dict[str, Any]]``
    Map from 1-based line number to pragma dict for every line that
    contains a ``# zdc:`` comment.

``parse_pragma_str(text)`` → ``Dict[str, Any]``
    Parse a single pragma-body string (the part after ``# zdc:``).
"""
from __future__ import annotations

import ast
import io
import re
import tokenize as _tokenize
from typing import Any, Dict, Optional

# Matches the pragma marker and captures everything after the colon
_ZDC_RE = re.compile(r'#\s*zdc\s*:\s*(.*)', re.IGNORECASE)

# Split on commas, respecting simple quoted strings (not nested)
_ITEM_RE = re.compile(r'[^,]+')


def parse_pragma_str(text: str) -> Dict[str, Any]:
    """Parse the body of a ``# zdc:`` comment into a key/value dict.

    Args:
        text: The portion of the comment after ``# zdc:``.

    Returns:
        Dict mapping pragma names to their values.  Flag tokens map to
        ``True``; ``key=value`` tokens map to the parsed value.
    """
    result: Dict[str, Any] = {}
    for raw in _ITEM_RE.finditer(text):
        item = raw.group().strip()
        if not item:
            continue
        if '=' in item:
            key, _, val_str = item.partition('=')
            key = key.strip()
            val_str = val_str.strip()
            try:
                value: Any = ast.literal_eval(val_str)
            except (ValueError, SyntaxError):
                value = val_str  # keep as bare string
        else:
            key = item
            value = True
        result[key.lower()] = value
    return result


def scan_pragmas(source: str) -> Dict[int, Dict[str, Any]]:
    """Scan *source* text for ``# zdc:`` pragma comments.

    Args:
        source: Raw Python source text (as returned by
                ``inspect.getsource()``).

    Returns:
        Dict mapping 1-based line numbers to pragma dicts.  Only lines
        that contain a ``# zdc:`` comment are present.
    """
    result: Dict[int, Dict[str, Any]] = {}
    for lineno, line in enumerate(source.splitlines(), start=1):
        m = _ZDC_RE.search(line)
        if m:
            pragmas = parse_pragma_str(m.group(1))
            if pragmas:
                result[lineno] = pragmas
    return result


def scan_line_comments(source: str) -> Dict[int, str]:
    """Scan *source* text for ordinary (non-pragma) ``#`` comments.

    Uses ``tokenize`` so ``#`` characters inside string literals are
    correctly ignored.  Pragma lines (``# zdc: ...``) are excluded because
    they are already handled by :func:`scan_pragmas`.

    Args:
        source: Raw Python source text.

    Returns:
        Dict mapping 1-based line numbers to the comment text (the ``#``
        and any leading whitespace stripped).  Only lines that carry a
        non-pragma comment token are included.
    """
    result: Dict[int, str] = {}
    try:
        tokens = _tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, tok_string, tok_start, _, _ in tokens:
            if tok_type == _tokenize.COMMENT:
                lineno = tok_start[0]
                # Strip leading '#' and whitespace
                text = tok_string.lstrip('#').strip()
                # Exclude pragma lines — those belong to scan_pragmas()
                if not _ZDC_RE.match(tok_string):
                    result[lineno] = text
    except _tokenize.TokenError:
        pass
    return result
