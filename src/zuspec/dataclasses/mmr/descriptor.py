"""Field descriptor: reg_field() factory and FieldAttr presets."""
from __future__ import annotations
from typing import Optional, Union
from .enums import SW, HW, RegAcc, OnWrite, OnRead, StickyBit, Precedence


def _coerce_sw(val) -> SW:
    """Accept SW, RegAcc, or int; return SW."""
    if isinstance(val, SW):
        return val
    if isinstance(val, RegAcc):
        return val.as_sw()
    return SW(val)


def _coerce_hw(val) -> HW:
    """Accept HW, RegAcc, or int; return HW."""
    if isinstance(val, HW):
        return val
    if isinstance(val, RegAcc):
        return val.as_hw()
    return HW(val)


def _coerce_onwrite(val):
    """Accept OnWrite enum or string or None; return string or None."""
    if val is None:
        return None
    if isinstance(val, OnWrite):
        return val.value
    return val


def _coerce_onread(val):
    """Accept OnRead enum or string or None; return string or None."""
    if val is None:
        return None
    if isinstance(val, OnRead):
        return val.value
    return val


def _coerce_stickybit(val):
    """Accept StickyBit enum, bool, or string; return bool/string."""
    if isinstance(val, StickyBit):
        return val.value
    return val


def _coerce_precedence(val):
    """Accept Precedence enum or string; return string."""
    if isinstance(val, Precedence):
        return val.value
    return val

_VALID_ONWRITE = frozenset({
    'woset', 'woclr', 'wot', 'wzs', 'wzc', 'wzt', 'wclr', 'wset',
})
_VALID_ONREAD = frozenset({'rclr', 'rset'})
_VALID_STICKYBIT = frozenset({True, False, 'posedge', 'negedge', 'bothedge'})
_VALID_PRECEDENCE = frozenset({'sw', 'hw'})


class FieldDescriptor:
    """Carries all declared properties of a single register field.

    Instances are created by :func:`reg_field` and embedded as class-level
    default values in ``@zdc.reg`` inner classes.  Do not construct
    ``FieldDescriptor`` directly; use :func:`reg_field` or
    :class:`FieldAttr` presets instead.

    The ``_width`` attribute is ``None`` until injected by the ``@zdc.reg``
    processor, which reads the ``zdc.uN`` type annotation after the class
    body is evaluated.

    Attributes
    ----------
    sw : SW
        Software (bus) access policy.
    hw : HW
        Hardware access policy.
    onwrite : str | None
        Bus-write side-effect mode string (e.g. ``'woclr'``), or ``None``.
    onread : str | None
        Bus-read side-effect mode string (e.g. ``'rclr'``), or ``None``.
    singlepulse : bool
        Field auto-clears one delta after a non-zero SW write.
    stickybit : bool | str
        Interrupt-latch sensitivity (``False``, ``True``, ``'posedge'``,
        ``'negedge'``, or ``'bothedge'``).
    sticky : bool
        Plain HW set-and-hold without edge detection.
    we : bool
        Write-enable qualifier for HW writes.
    wel : bool
        Write-enable-lock qualifier for HW writes.
    hwset : bool
        HW input 1 sets the field; HW input 0 is a no-op.
    hwclr : bool
        HW input 0 clears the field; HW input 1 is a no-op.
    precedence : str
        ``'sw'`` or ``'hw'`` — who wins a simultaneous SW/HW write.
    lsb : int | None
        Explicit LSB in the packed register word, or ``None`` for auto.
    default : int
        Reset value.
    _width : int | None
        Bit width; filled by ``@zdc.reg`` from the ``zdc.uN`` annotation.
    """

    __slots__ = (
        'sw', 'hw', 'onwrite', 'onread',
        'singlepulse', 'stickybit', 'sticky',
        'we', 'wel', 'hwset', 'hwclr',
        'precedence', 'lsb', 'name', 'desc', 'default',
        '_width',   # injected by @zdc.reg; None until then
    )

    def __init__(
        self,
        sw:          Union[SW, RegAcc, int]             = SW.RW,
        hw:          Union[HW, RegAcc, int]             = HW.R,
        onwrite:     Optional[Union[str, OnWrite]]      = None,
        onread:      Optional[Union[str, OnRead]]       = None,
        singlepulse: bool                               = False,
        stickybit:   Union[bool, str, StickyBit]        = False,
        sticky:      bool                               = False,
        we:          bool                               = False,
        wel:         bool                               = False,
        hwset:       bool                               = False,
        hwclr:       bool                               = False,
        precedence:  Union[str, Precedence]             = 'sw',
        lsb:         Optional[int]                      = None,
        name:        Optional[str]                      = None,
        desc:        str                                = '',
        default:     int                                = 0,
    ):
        onwrite   = _coerce_onwrite(onwrite)
        onread    = _coerce_onread(onread)
        stickybit = _coerce_stickybit(stickybit)
        precedence = _coerce_precedence(precedence)

        if onwrite is not None and onwrite not in _VALID_ONWRITE:
            raise ValueError(
                f"Unknown onwrite={onwrite!r}; valid: {sorted(_VALID_ONWRITE)}"
            )
        if onread is not None and onread not in _VALID_ONREAD:
            raise ValueError(
                f"Unknown onread={onread!r}; valid: {sorted(_VALID_ONREAD)}"
            )
        if stickybit not in _VALID_STICKYBIT:
            raise ValueError(
                f"Unknown stickybit={stickybit!r}; valid: {sorted(str(v) for v in _VALID_STICKYBIT)}"
            )
        if precedence not in _VALID_PRECEDENCE:
            raise ValueError(
                f"Unknown precedence={precedence!r}; valid: {sorted(_VALID_PRECEDENCE)}"
            )

        self.sw          = _coerce_sw(sw)
        self.hw          = _coerce_hw(hw)
        self.onwrite     = onwrite
        self.onread      = onread
        self.singlepulse = singlepulse
        self.stickybit   = stickybit
        self.sticky      = sticky
        self.we          = we
        self.wel         = wel
        self.hwset       = hwset
        self.hwclr       = hwclr
        self.precedence  = precedence
        self.lsb         = lsb
        self.name        = name
        self.desc        = desc
        self.default     = default
        self._width      = None   # filled by @zdc.reg

    def __repr__(self) -> str:
        return (
            f"FieldDescriptor(sw={self.sw.name}, hw={self.hw.name}, "
            f"default={self.default}, width={self._width})"
        )


def reg_field(
    sw:          Union[SW, RegAcc, int]             = SW.RW,
    hw:          Union[HW, RegAcc, int]             = HW.R,
    onwrite:     Optional[Union[str, OnWrite]]      = None,
    onread:      Optional[Union[str, OnRead]]       = None,
    singlepulse: bool                               = False,
    stickybit:   Union[bool, str, StickyBit]        = False,
    sticky:      bool                               = False,
    we:          bool                               = False,
    wel:         bool                               = False,
    hwset:       bool                               = False,
    hwclr:       bool                               = False,
    precedence:  Union[str, Precedence]             = 'sw',
    lsb:         Optional[int]                      = None,
    name:        Optional[str]                      = None,
    desc:        str                                = '',
    default:     int                                = 0,
) -> FieldDescriptor:
    """Declare a register field with explicit access-type parameters.

    Used as the default value for a field annotation inside a ``@zdc.reg``
    inner class.  The field's bit width is inferred from the ``zdc.uN`` type
    annotation on the class attribute.

    Parameters
    ----------
    sw : SW | RegAcc | int, default SW.RW
        Software (bus) access policy.  Controls whether bus reads/writes
        are honoured or silently discarded.  Accepts :class:`SW`,
        :class:`RegAcc`, or the raw integer value.
    hw : HW | RegAcc | int, default HW.R
        Hardware access policy.  Controls whether ``_hw_assign()`` drives
        the field (``HW.W`` / ``HW.RW``) or the field is read-only to HW
        (``HW.R``).  Accepts :class:`HW`, :class:`RegAcc`, or int.
    onwrite : OnWrite | str | None, default None
        Bus-write side-effect.  ``None`` means a plain masked write.
        String aliases (e.g. ``'woclr'``) and :class:`OnWrite` enum values
        are both accepted.
    onread : OnRead | str | None, default None
        Bus-read side-effect.  ``None`` means a plain read with no side
        effect.  String aliases (e.g. ``'rclr'``) and :class:`OnRead` enum
        values are both accepted.
    singlepulse : bool, default False
        If ``True``, the field auto-clears to 0 one simulation delta after
        a SW write of a non-zero value.  Hardware can read the 1 in the same
        delta before it clears.
    stickybit : StickyBit | bool | str, default False
        Edge-sensitivity for HW interrupt-pending bits.  ``False`` disables
        stickybit logic (plain HW write).  ``True`` / ``StickyBit.LEVEL``
        sets on any high input; ``'posedge'`` / ``StickyBit.POSEDGE`` sets
        on 0→1 transition only.
    sticky : bool, default False
        Plain sticky: once set by HW, remains set until SW clears it
        (no edge detection, no stickybit semantics).
    we : bool, default False
        Write-enable qualifier: hardware must assert a companion ``_we``
        signal for ``_hw_assign`` to take effect.
    wel : bool, default False
        Write-enable-lock: like ``we`` but locked until reset.
    hwset : bool, default False
        If ``True``, ``_hw_assign(1)`` sets the field; ``_hw_assign(0)``
        has no effect (the HW input is treated as a one-shot set strobe).
    hwclr : bool, default False
        If ``True``, ``_hw_assign(0)`` clears the field; ``_hw_assign(1)``
        has no effect (the HW input is treated as a one-shot clear strobe).
    precedence : Precedence | str, default 'sw'
        When SW and HW write in the same simulation delta, this determines
        whose value is stored.  ``'hw'`` / ``Precedence.HW`` gives hardware
        priority.
    lsb : int | None, default None
        Explicit LSB position in the packed register word.  If ``None``,
        the ``@zdc.reg`` processor assigns positions automatically in
        declaration order.
    name : str | None, default None
        Override the field name (for generated artefacts only; does not
        affect Python attribute access).
    desc : str, default ''
        Human-readable description, included in generated register maps and
        SW artefacts.
    default : int, default 0
        Reset value.  Must fit within the field's bit width.

    Returns
    -------
    FieldDescriptor
        An opaque descriptor consumed by ``@zdc.reg``; do not use it
        directly as a runtime value.

    Examples
    --------
    Interrupt-pending bit (write-one-clear, posedge HW latch)::

        DONE: zdc.u1 = zdc.reg_field(
            sw=zdc.SW.RW, onwrite='woclr',
            stickybit='posedge', hw=zdc.HW.W, hwset=True,
        )

    Hardware-driven status register, read-only from SW::

        BUSY: zdc.u8 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W,
                                    hwset=True, hwclr=True, default=0)
    """
    return FieldDescriptor(
        sw=sw, hw=hw, onwrite=onwrite, onread=onread,
        singlepulse=singlepulse, stickybit=stickybit, sticky=sticky,
        we=we, wel=wel, hwset=hwset, hwclr=hwclr,
        precedence=precedence, lsb=lsb, name=name, desc=desc, default=default,
    )


# ---------------------------------------------------------------------------
# FieldAttr presets
# ---------------------------------------------------------------------------

class _Preset:
    """A FieldAttr preset that can be used bare or called with default=."""

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def __call__(self, *, default: int = 0) -> FieldDescriptor:
        return FieldDescriptor(**{**self._kwargs, 'default': default})

    # Allow bare usage: `FIELD: zdc.u1 = FieldAttr.StickyBit`
    # The @zdc.reg processor checks isinstance(value, (FieldDescriptor, _Preset))
    # and calls _to_descriptor() to materialise with default=0.
    def _to_descriptor(self, default: int = 0) -> FieldDescriptor:
        return FieldDescriptor(**{**self._kwargs, 'default': default})

    def __repr__(self) -> str:
        return f"FieldAttr preset({self._kwargs})"


class FieldAttr:
    """Shorthand preset field descriptors for the most common field types.

    Each member is a :class:`_Preset` that may be used bare (``default=0``)
    or called with an explicit ``default=`` value::

        FIELD_A: zdc.u8 = FieldAttr.RW(default=0xFF)
        DONE:    zdc.u1 = FieldAttr.StickyBit          # default=0 implied

    Preset summary:

    ============  ===  ===  =========  ========  =======
    Preset        SW   HW   onwrite    stickybit  hwset/hwclr
    ============  ===  ===  =========  ========  =======
    RW            RW   R    —          —          —
    RO            RO   W    —          —          hwset+hwclr
    W1S           RW   RW   woset      —          —
    W1C           RW   W    woclr      —          hwset
    WO            WO   R    —          —          —
    Pulse         RW   R    —          —          singlepulse
    StickyBit     RW   W    woclr      posedge    hwset
    ============  ===  ===  =========  ========  =======
    """

    #: General read-write configuration field.
    RW = _Preset(sw=SW.RW, hw=HW.R)

    #: Read-only status field; hardware drives it.
    RO = _Preset(sw=SW.RO, hw=HW.W, hwset=True, hwclr=True)

    #: Write-one-set; hardware reads back the accumulated value.
    W1S = _Preset(sw=SW.RW, onwrite='woset', hw=HW.RW)

    #: Write-one-clear; hardware may set individual bits.
    W1C = _Preset(sw=SW.RW, onwrite='woclr', hw=HW.W, hwset=True)

    #: Write-only command field; reads return 0.
    WO = _Preset(sw=SW.WO, hw=HW.R)

    #: Single-pulse command strobe; self-clears one cycle after SW write.
    Pulse = _Preset(sw=SW.RW, singlepulse=True, hw=HW.R)

    #: Interrupt-pending bit: posedge-sensitive OR-accumulate, woclr.
    StickyBit = _Preset(
        sw=SW.RW, onwrite='woclr',
        stickybit='posedge', hw=HW.W, hwset=True,
    )
