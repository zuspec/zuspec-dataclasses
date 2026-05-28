"""SDC (Synopsys Design Constraints) emitter for zuspec-dataclasses.

Walks an elaborated component hierarchy and produces Tcl/SDC text suitable
for passing to standard synthesis and static-timing-analysis tools (Yosys,
Vivado, Quartus, OpenROAD, etc.).

Public API::

    from zuspec.dataclasses.sdc_emit import SDCEmitPass, emit_sdc

    # Quick helper — returns the SDC string for an elaborated top component.
    sdc = emit_sdc(top)

    # Fine-grained control.
    p = SDCEmitPass()
    p.visit(top)
    print(p.sdc_text())

Output sections
---------------

1. **create_clock** — one per unique root :class:`ClockDomain` that has a
   non-``None`` ``period`` or ``period_ns``.

2. **create_generated_clock** — one per :class:`DerivedClockDomain` (``div``
   or ``mul`` != 1).

3. **set_false_path** for CDC — one pair per pair of domains that share a
   signal crossing, unless the crossing passes through a
   :class:`~zuspec.dataclasses.cdc.TwoFFSync` or
   :class:`~zuspec.dataclasses.cdc.AsyncFIFO` (which carry their own SDC).

4. **set_false_path** for reset sequencing — emitted when a
   :class:`ResetDomain` has ``release_after`` set.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Set, Tuple

from .domain import (
    ClockDomain,
    DerivedClockDomain,
    InheritedDomain,
    ResetDomain,
    _ClockDomainField,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STOP_NAMES: frozenset = frozenset({"Component", "SyncComponent", "TypeBase", "object"})


def _iter_named_domains(comp) -> List[Tuple[str, ClockDomain]]:
    """Return ``(attr_name, domain_instance)`` for every :class:`ClockDomain`
    declared on *comp*'s class (via MRO walk, stopping at framework base classes).
    """
    seen_names: Set[str] = set()
    results: List[Tuple[str, ClockDomain]] = []
    for cls in type(comp).__mro__:
        if cls.__name__ in _STOP_NAMES:
            break
        for name, val in vars(cls).items():
            if name in seen_names:
                continue
            seen_names.add(name)
            if isinstance(val, ClockDomain):
                results.append((name, val))
            elif isinstance(val, _ClockDomainField):
                # Resolve the per-instance ClockDomain via the descriptor.
                resolved = getattr(comp, name, None)
                if isinstance(resolved, ClockDomain):
                    results.append((name, resolved))
    return results


def _iter_children(comp):
    """Yield direct child Component instances from *comp*'s ``_domain_children``."""
    impl = getattr(comp, '_impl', None)
    if impl is None:
        return
    for child in getattr(impl, '_domain_children', []):
        yield child


def _clock_name(domain: ClockDomain, attr_name: str) -> str:
    """Return the SDC clock name for *domain*."""
    if domain.name:
        return domain.name
    return attr_name or "clk"


def _period_ns(domain: ClockDomain) -> Optional[float]:
    """Return the period in nanoseconds, or ``None``."""
    if domain.period is None:
        return None
    if hasattr(domain.period, "as_ns"):
        return float(domain.period.as_ns())
    if hasattr(domain.period, "ns"):
        return float(domain.period.ns)
    try:
        return float(domain.period)
    except (TypeError, ValueError):
        return None


def _source_period_ns(domain: "DerivedClockDomain",
                      source_domain: Optional[ClockDomain]) -> Optional[float]:
    """Compute derived period: source_period * div / mul."""
    if source_domain is None:
        return None
    base = _period_ns(source_domain)
    if base is None:
        return None
    if domain.mul and domain.mul != 1:
        base = base / domain.mul
    if domain.div and domain.div != 1:
        base = base * domain.div
    return base


def _is_cdc_safe(comp) -> bool:
    """Return True if *comp* is a known CDC-safe primitive (TwoFFSync, AsyncFIFO,
    or tagged with ``_cdc_unchecked``)."""
    t = type(comp)
    if getattr(t, '_zdc_two_ff_sync', False):
        return True
    if getattr(t, '_cdc_unchecked', False):
        return True
    # AsyncFIFO check by class name (avoids circular import)
    if t.__name__ == "AsyncFIFO":
        return True
    return False


# ---------------------------------------------------------------------------
# SDCEmitPass
# ---------------------------------------------------------------------------

class SDCEmitPass:
    """Walk an elaborated component tree and accumulate SDC statements.

    Usage::

        p = SDCEmitPass()
        p.visit(top)
        text = p.sdc_text()
    """

    def __init__(self) -> None:
        # Maps ClockDomain id() → (attr_name, ClockDomain)
        self._seen_clocks: Dict[int, Tuple[str, ClockDomain]] = {}
        # (source_clock_id, dest_clock_id) → True — domain pairs already seen
        self._cdc_pairs: Set[Tuple[int, int]] = set()
        # Reset sequencing: (release_after domain id, domain id) → True
        self._reset_seq: Set[Tuple[int, int]] = set()
        # Collected lines per section
        self._create_clock_lines: List[str] = []
        self._generated_clock_lines: List[str] = []
        self._false_path_lines: List[str] = []

    # ------------------------------------------------------------------
    # Public

    def visit(self, comp, parent_domain: Optional[ClockDomain] = None) -> None:
        """Recursively walk *comp* and its children, accumulating SDC."""
        self._process_component(comp, parent_domain)

    def sdc_text(self) -> str:
        """Return the accumulated SDC as a single string."""
        buf = io.StringIO()
        if self._create_clock_lines:
            buf.write("# ---- Clock definitions ----\n")
            for line in self._create_clock_lines:
                buf.write(line + "\n")
            buf.write("\n")
        if self._generated_clock_lines:
            buf.write("# ---- Derived / generated clocks ----\n")
            for line in self._generated_clock_lines:
                buf.write(line + "\n")
            buf.write("\n")
        if self._false_path_lines:
            buf.write("# ---- False paths (CDC crossings & reset sequencing) ----\n")
            for line in self._false_path_lines:
                buf.write(line + "\n")
            buf.write("\n")
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Internal

    def _process_component(self, comp, parent_domain: Optional[ClockDomain]) -> None:
        """Process one component: register its domains and recurse into children."""
        resolved_clock = (
            comp.__dict__.get('_zdc_resolved_clock_domain')
            or getattr(type(comp), 'clock_domain', None)
        )
        resolved_reset = (
            comp.__dict__.get('_zdc_resolved_reset_domain')
            or getattr(type(comp), 'reset_domain', None)
        )

        # Register named domains on this component
        for attr_name, domain in _iter_named_domains(comp):
            self._register_clock(attr_name, domain, parent_domain)

        # Emit reset sequencing false paths
        if isinstance(resolved_reset, ResetDomain) and resolved_reset.release_after:
            after = resolved_reset.release_after
            pair = (id(after), id(resolved_reset))
            if pair not in self._reset_seq:
                self._reset_seq.add(pair)
                # Use names if available
                after_name = getattr(after, 'name', None) or "rst_after"
                self_name  = getattr(resolved_reset, 'name', None) or "rst_self"
                self._false_path_lines.append(
                    f"# Reset sequencing: {self_name} releases after {after_name}"
                )
                self._false_path_lines.append(
                    f"set_false_path -from [get_nets {{{after_name}}}]"
                    f" -to [get_nets {{{self_name}}}]"
                )

        # Check CDC: does this component's domain differ from its parent's?
        if (parent_domain is not None
                and resolved_clock is not None
                and resolved_clock is not parent_domain
                and not _is_cdc_safe(comp)):
            pair = (id(parent_domain), id(resolved_clock))
            rev_pair = (id(resolved_clock), id(parent_domain))
            if pair not in self._cdc_pairs and rev_pair not in self._cdc_pairs:
                self._cdc_pairs.add(pair)
                src_name = self._clock_name_by_id(id(parent_domain))
                dst_name = self._clock_name_by_id(id(resolved_clock))
                if src_name and dst_name and src_name != dst_name:
                    self._false_path_lines.append(
                        f"# CDC crossing: {src_name} → {dst_name}"
                    )
                    self._false_path_lines.append(
                        f"set_false_path"
                        f" -from [get_clocks {{{src_name}}}]"
                        f" -to   [get_clocks {{{dst_name}}}]"
                    )

        # Recurse into children
        for child in _iter_children(comp):
            self._process_component(child, resolved_clock or parent_domain)

    def _register_clock(
        self,
        attr_name: str,
        domain: ClockDomain,
        parent_domain: Optional[ClockDomain],
    ) -> None:
        """Emit create_clock / create_generated_clock for *domain* (once only)."""
        if id(domain) in self._seen_clocks:
            return
        self._seen_clocks[id(domain)] = (attr_name, domain)
        name = _clock_name(domain, attr_name)

        if isinstance(domain, DerivedClockDomain):
            # Resolve source domain
            source = domain.source
            source_domain: Optional[ClockDomain] = None
            if isinstance(source, InheritedDomain):
                source_domain = parent_domain
            elif isinstance(source, ClockDomain):
                source_domain = source
            elif callable(source):
                # lambda form — we can't resolve without a comp instance here;
                # treat as unknown source
                source_domain = None

            source_name = (
                self._clock_name_by_id(id(source_domain))
                if source_domain is not None
                else None
            )

            period = _source_period_ns(domain, source_domain)
            period_str = f" # period ≈ {period:.3f} ns" if period is not None else ""

            div_part = f" -divide_by {domain.div}" if domain.div and domain.div != 1 else ""
            mul_part = f" -multiply_by {domain.mul}" if domain.mul and domain.mul != 1 else ""
            src_part = (
                f" -source [get_clocks {{{source_name}}}]"
                if source_name else ""
            )
            self._generated_clock_lines.append(
                f"create_generated_clock -name {{{name}}}{src_part}{div_part}{mul_part}"
                f"{period_str}"
            )
        else:
            period = _period_ns(domain)
            if period is not None:
                self._create_clock_lines.append(
                    f"create_clock -name {{{name}}} -period {period:.3f}"
                )

    def _clock_name_by_id(self, domain_id: int) -> Optional[str]:
        """Look up the SDC name for a previously registered domain."""
        entry = self._seen_clocks.get(domain_id)
        if entry is None:
            return None
        attr_name, domain = entry
        return _clock_name(domain, attr_name)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def emit_sdc(comp) -> str:
    """Walk the elaborated component *comp* and return SDC constraint text.

    :param comp: The elaborated top-level component instance.
    :returns: A string of SDC/Tcl commands.

    Example::

        import zuspec.dataclasses as zdc
        from zuspec.dataclasses.sdc_emit import emit_sdc

        @zdc.dataclass
        class Top(zdc.SyncComponent):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="sys_clk")
            ...

        async with zdc.simulate(Top) as top:
            print(emit_sdc(top))
    """
    p = SDCEmitPass()
    p.visit(comp)
    return p.sdc_text()
