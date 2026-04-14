"""Structured error types for Zuspec hardware design errors.

All public Zuspec error conditions raise a subclass of :class:`ZuspeccError`,
which formats a human-readable message that includes the component path, field
name, source location, and an actionable hint where available.

Usage example::

    raise ZuspeccWidthError(
        "Output width mismatch",
        component="Counter",
        field="count",
        hint="Declare 'count' with width=8 to match the 8-bit target.",
        source_file=__file__,
        source_line=42,
    )
"""
from __future__ import annotations


class ZuspeccError(Exception):
    """Base class for all Zuspec hardware design errors.

    :param message: Human-readable description of what went wrong.
    :type message: str
    :param component: Dotted path of the component where the error occurred.
    :type component: str
    :param field: Name of the signal/field involved, if applicable.
    :type field: str
    :param hint: Actionable suggestion for resolving the error.
    :type hint: str
    :param source_file: Path to the Python source file that triggered the error.
    :type source_file: str
    :param source_line: Line number in *source_file*.
    :type source_line: int
    """

    def __init__(
        self,
        message: str,
        *,
        component: str = "",
        field: str = "",
        hint: str = "",
        source_file: str = "",
        source_line: int = 0,
    ) -> None:
        self.component = component
        self.field = field
        self.hint = hint
        self.source_file = source_file
        self.source_line = source_line
        super().__init__(self._format(message))

    def _format(self, message: str) -> str:
        lines = [f"\nZuspeccError: {message}"]
        if self.component:
            lines.append(f"  Component: {self.component}")
        if self.field:
            lines.append(f"  Field:     {self.field}")
        if self.source_file:
            loc = (f"{self.source_file}:{self.source_line}"
                   if self.source_line else self.source_file)
            lines.append(f"  Source:    {loc}")
        if self.hint:
            lines.append(f"  Hint:      {self.hint}")
        return "\n".join(lines)


class ZuspeccCDCError(ZuspeccError):
    """Clock domain crossing without a synchronizer.

    Raised when a signal driven in one clock domain is directly read by a
    process in a different clock domain with no intervening synchronizer.
    """


class ZuspeccWidthError(ZuspeccError):
    """Signal width mismatch.

    Raised when a source signal's declared width differs from the target
    port's or assignment destination's declared width.
    """


class ZuspeccSynthError(ZuspeccError):
    """Unsynthesizable construct in a synthesizable context.

    Raised when a Python construct (e.g. arbitrary function call, dynamic
    dispatch, external I/O) cannot be lowered to RTL.
    """


class ZuspeccConflictError(ZuspeccError):
    """Two ``@zdc.rule`` decorators with conflicting actions.

    Raised during elaboration when two rules assign incompatible values to
    the same output field within the same clock cycle.
    """
