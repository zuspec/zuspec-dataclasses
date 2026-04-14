"""Pass — abstract base class for IR transformation passes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Type


class Pass(ABC):
    """Abstract base for all transformation passes.

    Subclasses must implement :py:meth:`name` and :py:meth:`run`.

    Type-parametric design: both synthesis and C-gen backends can specialise
    by accepting/returning their own IR types.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique human-readable name for this pass."""

    @abstractmethod
    def run(self, ir: Any) -> Any:
        """Execute this pass.

        Args:
            ir: The current IR state (type depends on the pipeline).

        Returns:
            The transformed IR (may be the same object or a new one).
        """

    def produces_domain_types(self) -> List[Type]:
        """Return a list of ``DomainNode`` subclasses that this pass introduces.

        The default returns an empty list (most passes produce no domain nodes).
        ``PassManager.validate()`` checks that for every type listed here, the
        corresponding lowering pass appears later in the pipeline.
        """
        return []
