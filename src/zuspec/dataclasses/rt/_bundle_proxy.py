from __future__ import annotations
import dataclasses as dc
from typing import Any, Dict, Set


class BundleProxy:
    """Proxy for bundle fields that stores signals on the owning component.

    Signals are stored in the owning component's `_impl._signal_values` under
    the name `{bundle_field}.{signal}`.
    """

    def __init__(
        self,
        comp,
        bundle_field: str,
        const_fields: Dict[str, Any],
        signal_dirs: Dict[str, str],
        signal_widths: Dict[str, int],
    ):
        object.__setattr__(self, "_comp", comp)
        object.__setattr__(self, "_bundle_field", bundle_field)
        object.__setattr__(self, "_const_fields", const_fields)
        object.__setattr__(self, "_signal_dirs", signal_dirs)
        object.__setattr__(self, "_signal_widths", signal_widths)

    @property
    def _signal_fields(self) -> Set[str]:
        return set(object.__getattribute__(self, "_signal_dirs").keys())

    def _full(self, name: str) -> str:
        return f"{object.__getattribute__(self, '_bundle_field')}.{name}"

    def __getattr__(self, name: str):
        const_fields = object.__getattribute__(self, "_const_fields")
        if name in const_fields:
            return const_fields[name]

        signal_dirs = object.__getattribute__(self, "_signal_dirs")
        if name in signal_dirs:
            comp = object.__getattribute__(self, "_comp")
            return comp._impl.signal_read(comp, self._full(name))

        raise AttributeError(name)

    def __setattr__(self, name: str, value):
        const_fields = object.__getattribute__(self, "_const_fields")
        if name in const_fields:
            raise AttributeError(f"Cannot modify const field '{name}'")

        signal_dirs = object.__getattribute__(self, "_signal_dirs")
        if name in signal_dirs:
            if signal_dirs[name] == "in":
                raise AttributeError(f"Cannot drive input signal '{name}'")
            comp = object.__getattribute__(self, "_comp")
            widths = object.__getattribute__(self, "_signal_widths")
            comp._impl.signal_write(comp, self._full(name), value, widths.get(name, 32))
            return

        raise AttributeError(name)
