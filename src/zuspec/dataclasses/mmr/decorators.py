"""@zdc.reg and @zdc.regfile decorators for register-file declaration."""
from __future__ import annotations

import types
from typing import Optional

from .descriptor import FieldDescriptor, _Preset
from .field_rt import FieldRT
from .register_rt import RegisterRT

# Sentinel attached to inner register classes by @zdc.reg
_REG_MARKER = '__zdc_reg__'
# Sentinel attached to RegisterFile subclasses by @zdc.regfile
_REGFILE_MARKER = '__zdc_regfile__'


def reg(
    offset: int,
    width:  int = 32,
    desc:   str = '',
):
    """Class decorator that marks an inner class as a register declaration.

    Example::

        @zdc.reg(offset=0x04)
        class STATUS:
            BUSY:  zdc.u1 = zdc.reg_field(sw=zdc.SW.RO, hw=zdc.HW.W, default=0)
            DONE:  zdc.u1 = zdc.FieldAttr.StickyBit
    """
    def _decorator(cls):
        # Collect and validate field descriptors from class annotations
        annotations = cls.__dict__.get('__annotations__', {})
        fields_meta = []  # list of (attr_name, FieldDescriptor)

        for attr_name, ann_type in annotations.items():
            raw_val = cls.__dict__.get(attr_name)
            if raw_val is None:
                continue
            if isinstance(raw_val, _Preset):
                fd = raw_val._to_descriptor(default=0)
            elif isinstance(raw_val, FieldDescriptor):
                fd = raw_val
            else:
                continue  # not a field descriptor

            # Inject width from zdc.uN annotation
            bit_width = _extract_width(ann_type, attr_name)
            import copy
            fd = copy.copy(fd)
            fd._width = bit_width
            fd.default = fd.default & ((1 << bit_width) - 1)
            if fd.name is None:
                fd.name = attr_name
            fields_meta.append((attr_name, fd))

        # Assign auto lsb values where lsb=None; check for overlaps
        _assign_lsbs(fields_meta, attr_name=cls.__name__, reg_width=width)

        # Attach metadata to the class
        cls.__zdc_reg__ = True
        cls._mmr_offset  = offset
        cls._mmr_width   = width
        cls._mmr_desc    = desc
        cls._mmr_fields  = fields_meta   # [(attr_name, FieldDescriptor)]

        return cls
    return _decorator


def regfile(cls):
    """Class decorator for RegisterFile subclasses.

    Collects all ``@zdc.reg``-decorated inner classes and attaches the
    elaboration metadata to the class.  Actual ``FieldRT`` / ``RegisterRT``
    instances are created per-instance at elaboration time via
    :meth:`~zuspec.dataclasses.mmr.base.RegisterFile._elaborate`.
    """
    reg_classes = []  # list of (attr_name, inner_cls)
    for name, val in vars(cls).items():
        if isinstance(val, type) and getattr(val, _REG_MARKER, False):
            reg_classes.append((name, val))

    cls._mmr_reg_classes = reg_classes
    cls.__zdc_regfile__  = True
    return cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_width(ann_type, field_name: str) -> int:
    """Extract bit width from a ``zdc.uN`` (Annotated) type annotation."""
    # zdc.uN is Annotated[int, U(N)] where U carries .width
    from ..types import U, S
    import typing

    # Try __metadata__ (typing.Annotated style)
    metadata = getattr(ann_type, '__metadata__', None)
    if metadata:
        for item in metadata:
            if isinstance(item, (U, S)):
                return item.width

    # Try get_args fallback
    try:
        args = typing.get_args(ann_type)
        for item in args:
            if isinstance(item, (U, S)):
                return item.width
    except Exception:
        pass

    raise TypeError(
        f"Cannot determine bit width for field '{field_name}': "
        f"annotation {ann_type!r} is not a zdc.uN / zdc.sN type."
    )


def _assign_lsbs(fields_meta: list, attr_name: str, reg_width: int) -> None:
    """Fill in auto lsb values and check for bit-range overlaps."""
    occupied: dict[int, str] = {}  # bit_index → field name
    auto_cursor = 0

    for fname, fd in fields_meta:
        if fd.lsb is None:
            fd.lsb = auto_cursor
        lsb = fd.lsb
        for bit in range(lsb, lsb + fd._width):
            if bit >= reg_width:
                raise ValueError(
                    f"Field '{fname}' in register '{attr_name}' extends "
                    f"beyond register width {reg_width} at bit {bit}."
                )
            if bit in occupied:
                raise ValueError(
                    f"Field '{fname}' overlaps with '{occupied[bit]}' "
                    f"at bit {bit} in register '{attr_name}'."
                )
            occupied[bit] = fname
        auto_cursor = lsb + fd._width
