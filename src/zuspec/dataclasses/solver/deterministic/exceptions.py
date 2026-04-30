"""Exceptions raised by the deterministic constraint evaluation path."""
from __future__ import annotations

from typing import Any


class PreconditionViolation(Exception):
    """Raised when a requires-role or zero-open-var constraint is not satisfied.

    Parameters
    ----------
    constraint_name:
        Human-readable name of the constraint (e.g. ``"Decode.c_valid_opcode"``).
    obj:
        The action object being evaluated (for debug output).
    """

    def __init__(self, constraint_name: str, obj: Any = None):
        self.constraint_name = constraint_name
        self.obj = obj
        super().__init__(
            f"Precondition violated: {constraint_name}"
            + (f" on {obj!r}" if obj is not None else "")
        )
