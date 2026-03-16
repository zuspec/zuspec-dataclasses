"""Back-end abstraction types for the Zuspec solver."""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class SolverBackend(Protocol):
    """Protocol that every solver back-end must satisfy.

    Any class that implements the three abstract members below satisfies this
    interface without explicit inheritance.  ``@runtime_checkable`` lets the
    registry validate back-ends with ``isinstance(backend, SolverBackend)``.
    """

    @property
    def name(self) -> str:
        """Short identifier: ``"python"``, ``"native"``, etc."""
        ...

    @property
    def available(self) -> bool:
        """``True`` when this back-end can be used on the current host."""
        ...

    def randomize(
        self,
        obj: Any,
        seed: Optional[int] = None,
        timeout_ms: Optional[int] = 1000,
    ) -> None:
        """Randomize all rand/randc fields in *obj*.

        Updates *obj* in place.  Raises ``RandomizationError`` on UNSAT or
        timeout.  Must never import from the other back-end's modules.
        """
        ...

    def randomize_with(
        self,
        obj: Any,
        with_block: Any,
        seed: Optional[int] = None,
        timeout_ms: Optional[int] = 1000,
    ) -> None:
        """Randomize *obj* with extra inline constraints from *with_block*.

        *with_block* is an opaque object produced by the ``randomize_with``
        context manager after parsing the ``with`` statement body.
        """
        ...
