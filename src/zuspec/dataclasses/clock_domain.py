"""Re-exports for backward compatibility and convenience.

The canonical ClockDomain and clock_domain() factory live in
:mod:`zuspec.dataclasses.domain`.  This module re-exports them so that
existing imports of ``from .clock_domain import ClockDomain`` continue to work.
"""

from .domain import ClockDomain, clock_domain, _ClockDomainField

__all__ = ["ClockDomain", "clock_domain", "_ClockDomainField"]
