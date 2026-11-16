"""A component's class-level ``ClockDomain``/``ResetDomain`` as the domain IR
(``zuspec.ir.core.domain``).

zdc names a clock per class; the domain IR has a domain object per
declaration, kinds, associations and drivers. The mapping is what a domain
IR top does with a root domain: the class creates the domain (a
``DomainDecl`` named after the attribute), makes it its own default (a
``DomainAssoc`` with ``target=[]``) and drives it from the port synthesis
gives it (a ``DomainDriver``):

- a clock's port is ``ClockDomain.name``, else ``clk``; its params are
  ``div``, ``mul``, ``phase_deg`` and, when known, ``period`` in
  femtoseconds (the one param outside the library kind's);
- a reset's port is ``rst_n`` or ``rst`` after its polarity, which is the
  driver's ``active_low``; its ``style`` param is 0 (async) or 1 (sync). A
  reset of style ``none`` has no pin: it has no driver, and ``style`` 1.

The kinds are the library kinds ``fw_clock_kind`` and ``fw_reset_kind``,
defined as the fw-hdl spec's SV classes define them.

A ``DerivedClockDomain``'s source is not recorded: ``super()`` (the
parent's domain) has no ``DomainRef`` form, and a lambda source names an
attribute the factory does not otherwise read. Domain overrides in
``__bind__`` are applied by the Python runtime only, and are not mapped.

See fw-hdl ``docs/design/core-domains-plan.md``, "D8 design".
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import zuspec.ir.core as ir

CLOCK = "fw_clock_kind"
RESET = "fw_reset_kind"

# fw_reset_kind::style_e
STYLE_ASYNC, STYLE_SYNC, STYLE_ANY = 0, 1, 2

_FS = {"S": 15, "MS": 12, "US": 9, "NS": 6, "PS": 3, "FS": 0}


def _c(v) -> ir.ExprConstant:
    return ir.ExprConstant(value=v)


def _sev(same, related, unrelated) -> Dict[str, ir.DomainSeverity]:
    return {"same": ir.DomainSeverity[same], "related": ir.DomainSeverity[related],
            "unrelated": ir.DomainSeverity[unrelated]}


def clock_kind() -> ir.DataTypeDomainKind:
    """``fw_clock_kind``."""
    derivs = {"root": ir.DomainDerivDecl(sources=[])}
    for n in ("derived", "phase", "gated", "muxed"):
        derivs[n] = ir.DomainDerivDecl(sources=["from"])
    return ir.DataTypeDomainKind(
        name=CLOCK, physical=True, derivations=derivs,
        severities=_sev("NONE", "INFO", "ERROR"),
        pin_default={"unused": _c(0)}, port_names={"/unused=0": "clk"})


def reset_kind() -> ir.DataTypeDomainKind:
    """``fw_reset_kind``."""
    derivs = {"root": ir.DomainDerivDecl(sources=[])}
    for n in ("synced", "combined", "software"):
        derivs[n] = ir.DomainDerivDecl(sources=["from"])
    return ir.DataTypeDomainKind(
        name=RESET, physical=True, derivations=derivs,
        severities=_sev("NONE", "WARNING", "ERROR"),
        pin_default={"active_low": _c(0), "style": _c(STYLE_ANY)},
        port_names={f"/active_low={lo},style={STYLE_ANY}": "rst_n" if lo else "rst"
                    for lo in (0, 1)},
        polarity="active_low")


def period_fs(period: Any) -> Optional[int]:
    """A zdc ``Time`` in femtoseconds, or None."""
    if period is None:
        return None
    return round(period.amt * 10 ** _FS[period.unit.name])


def _clock(an: str, cd: Any) -> Tuple[ir.DomainDecl, ir.DomainDriver]:
    from .domain import DerivedClockDomain
    params = {"div": _c(1), "mul": _c(1), "phase_deg": _c(0)}
    deriv = "root"
    if isinstance(cd, DerivedClockDomain):
        deriv = "derived"
        params = {"div": _c(cd.div), "mul": _c(cd.mul), "phase_deg": _c(cd.phase * 360)}
    p = period_fs(cd.period)
    if p is not None:
        params["period"] = _c(p)
    decl = ir.DomainDecl(name=an, kind=CLOCK, deriv=deriv, params=params)
    drv = ir.DomainDriver(domain=ir.DomainRef(decl=an), signal=[cd.name or "clk"])
    return decl, drv


def _reset(an: str, rd: Any) -> Tuple[ir.DomainDecl, Optional[ir.DomainDriver]]:
    from .domain import ResetPolarity, ResetStyle
    style = STYLE_ASYNC if rd.style == ResetStyle.ASYNC else STYLE_SYNC
    decl = ir.DomainDecl(name=an, kind=RESET, params={"style": _c(style)})
    if rd.style == ResetStyle.NONE:
        return decl, None
    lo = 1 if rd.polarity == ResetPolarity.ACTIVE_LOW else 0
    drv = ir.DomainDriver(domain=ir.DomainRef(decl=an), signal=["rst_n" if lo else "rst"],
                          attr={"active_low": _c(lo), "style": _c(STYLE_ANY)})
    return decl, drv


def add_domains(t: ir.DataTypeComponent, type_m: Dict[str, Any],
                clock: Optional[Tuple[str, Any]], reset: Optional[Tuple[str, Any]]) -> None:
    """Write ``clock`` and ``reset`` (each ``(attribute name, domain)`` or
    None) into ``t``'s domain lists, and their kinds into ``type_m``."""
    for kn, dom, mk, kind in ((CLOCK, clock, _clock, clock_kind),
                              (RESET, reset, _reset, reset_kind)):
        if dom is None:
            continue
        type_m.setdefault(kn, kind())
        decl, drv = mk(*dom)
        t.domains.append(decl)
        t.domain_assocs.append(ir.DomainAssoc(target=[], kind=kn,
                                              domain=ir.DomainRef(decl=decl.name)))
        if drv is not None:
            t.domain_drivers.append(drv)
