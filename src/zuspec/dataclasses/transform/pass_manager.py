"""PassManager — runs an ordered sequence of passes and enforces readiness."""
from __future__ import annotations

from typing import Any, Iterable, List


class PassValidationError(Exception):
    """Raised by :py:meth:`PassManager.validate` when the pass sequence is invalid.

    Common cause: a pass declares that it produces a ``DomainNode`` subclass
    whose ``lowered_by`` pass does not appear later in the pipeline.
    """


class DomainNodeNotLoweredError(Exception):
    """Raised by :py:meth:`PassManager.verify_ready` when an unlowered
    ``DomainNode`` survives to the readiness check.

    The exception message includes provenance information from the node.
    """


def _collect_domain_nodes(obj: Any, seen: set) -> list:
    """Recursively walk ``obj`` and collect any ``DomainNode`` instances found."""
    import dataclasses as _dc
    from zuspec.dataclasses.ir.domain_node import DomainNode

    if id(obj) in seen:
        return []
    seen.add(id(obj))

    found = []
    if isinstance(obj, DomainNode):
        found.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_collect_domain_nodes(v, seen))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found.extend(_collect_domain_nodes(item, seen))
    elif _dc.is_dataclass(obj) and not isinstance(obj, type):
        for f in _dc.fields(obj):
            found.extend(_collect_domain_nodes(getattr(obj, f.name), seen))
    return found


class PassManager:
    """Runs a sequence of :py:class:`Pass` objects in order.

    Usage::

        pm = PassManager([p1, p2, p3])
        pm.validate()          # optional — checks domain-node coverage
        result = pm.run(ir)    # chains passes; each sees the previous output
        pm.verify_ready(result)  # raises if any DomainNode remains

    Args:
        passes: Ordered list of :py:class:`Pass` instances.
    """

    def __init__(self, passes: Iterable) -> None:
        self._passes: List = list(passes)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Check that the pass sequence is self-consistent.

        For every ``DomainNode`` type declared by a pass via
        ``produces_domain_types()``, the corresponding lowering pass (the one
        whose instance would be set as ``DomainNode.lowered_by``) must appear
        *after* the producing pass.

        Raises:
            PassValidationError: If any domain type lacks a downstream lowerer.
        """
        # Collect all domain types produced by each pass, and track which
        # pass classes appear later in the sequence.
        produced: list = []  # (domain_type, producer_index)
        for idx, p in enumerate(self._passes):
            for dt in p.produces_domain_types():
                produced.append((dt, idx))

        if not produced:
            return

        # For each produced domain type, look for a pass that is listed as
        # the lowerer.  We check by comparing the lowered_by annotation on
        # the domain type class itself (if present) or by looking for a pass
        # that declares it lowers the type.
        pass_classes_after: dict = {}
        for idx, p in enumerate(self._passes):
            pass_classes_after.setdefault(type(p), []).append(idx)

        for domain_type, producer_idx in produced:
            # Check if any pass after producer_idx handles this domain type.
            # Passes signal this via an optional `lowers_domain_types()` method
            # (mirrors `produces_domain_types`).
            lowered = False
            for idx in range(producer_idx + 1, len(self._passes)):
                p = self._passes[idx]
                lowers = getattr(p, "lowers_domain_types", lambda: [])()
                if domain_type in lowers:
                    lowered = True
                    break
            if not lowered:
                raise PassValidationError(
                    f"Pass produces DomainNode type '{domain_type.__name__}' "
                    f"but no lowering pass appears after it in the pipeline."
                )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, ir: Any) -> Any:
        """Execute all passes in sequence.

        Args:
            ir: Initial IR state.

        Returns:
            The IR after all passes have been applied.
        """
        for p in self._passes:
            ir = p.run(ir)
        return ir

    # ------------------------------------------------------------------
    # Readiness check
    # ------------------------------------------------------------------

    def verify_ready(self, ir: Any) -> None:
        """Walk *ir* and raise if any ``DomainNode`` remains unlowered.

        Args:
            ir: The final IR to inspect.

        Raises:
            DomainNodeNotLoweredError: If a ``DomainNode`` is found anywhere
                in *ir* (recursive walk through dicts and lists).
        """
        remaining = _collect_domain_nodes(ir, set())
        if remaining:
            node = remaining[0]
            prov = getattr(node, "provenance", None)
            prov_info = ""
            if prov is not None:
                prov_info = (
                    f" (introduced by '{prov.pass_name}': {prov.description})"
                )
            raise DomainNodeNotLoweredError(
                f"DomainNode of type '{type(node).__name__}' was not lowered"
                f"{prov_info}. "
                f"{len(remaining)} unlowered node(s) found."
            )
