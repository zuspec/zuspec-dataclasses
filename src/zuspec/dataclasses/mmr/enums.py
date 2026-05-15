"""Access-type enums for abstract MMR field declarations."""
from enum import IntEnum, Enum


class SW(IntEnum):
    """Software-side bus access policy for a register field."""
    RW = 0  # SW may read and write
    RO = 1  # SW may read only; writes are silently discarded
    WO = 2  # SW may write only; reads return 0
    NA = 3  # No SW access; field is reserved / padding


class HW(IntEnum):
    """Hardware-side access policy for a register field."""
    R  = 0  # HW reads only  (hwif_out.<field>.value)
    W  = 1  # HW writes only (hwif_in.<field>.next / hwset / hwclr)
    RW = 2  # HW reads and writes
    NA = 3  # No HW access


class RegAcc(Enum):
    """Combined SW/HW access type — simplified single enum.

    Maps to :class:`SW` / :class:`HW` values:
    - ``RW`` → SW.RW / HW.RW
    - ``R``  → SW.RO / HW.R
    - ``W``  → SW.WO / HW.W
    - ``NA`` → SW.NA / HW.NA
    """
    RW = "rw"
    R  = "r"
    W  = "w"
    NA = "na"

    def as_sw(self) -> SW:
        """Convert to the equivalent :class:`SW` value."""
        return {
            RegAcc.RW: SW.RW,
            RegAcc.R:  SW.RO,
            RegAcc.W:  SW.WO,
            RegAcc.NA: SW.NA,
        }[self]

    def as_hw(self) -> HW:
        """Convert to the equivalent :class:`HW` value."""
        return {
            RegAcc.RW: HW.RW,
            RegAcc.R:  HW.R,
            RegAcc.W:  HW.W,
            RegAcc.NA: HW.NA,
        }[self]


class OnWrite(Enum):
    """Bus-write side-effect modes (SystemRDL ``onwrite`` property).

    Passed as ``onwrite=OnWrite.WOCLR`` to :func:`reg_field`.
    """
    WOSET = "woset"  # write-one-set:     result = r | (d & strobe)
    WOCLR = "woclr"  # write-one-clear:   result = r & ~(d & strobe)
    WOT   = "wot"    # write-one-toggle:  result = r ^ (d & strobe)
    WZS   = "wzs"    # write-zero-set:    result = r | (~d & strobe)
    WZC   = "wzc"    # write-zero-clear:  result = r & (d | ~strobe)
    WZT   = "wzt"    # write-zero-toggle: result = r ^ (~d & strobe)
    WCLR  = "wclr"   # write-clears:      result = 0
    WSET  = "wset"   # write-sets:        result = all-ones


class OnRead(Enum):
    """Bus-read side-effect modes (SystemRDL ``onread`` property).

    Passed as ``onread=OnRead.RCLR`` to :func:`reg_field`.
    """
    RCLR = "rclr"  # read-clear: field is zeroed after every read
    RSET = "rset"  # read-set:   field is set to all-ones after every read


class StickyBit(Enum):
    """Stickybit trigger-sensitivity modes (SystemRDL ``stickybit`` property).

    Passed as ``stickybit=StickyBit.POSEDGE`` to :func:`reg_field`.
    """
    LEVEL    = True        # level-sensitive (any high input sets the bit)
    POSEDGE  = "posedge"   # rising-edge sensitive
    NEGEDGE  = "negedge"   # falling-edge sensitive
    BOTHEDGE = "bothedge"  # both-edge sensitive


class Precedence(Enum):
    """Simultaneous SW/HW write precedence (SystemRDL ``precedence`` property).

    Passed as ``precedence=Precedence.HW`` to :func:`reg_field`.
    """
    SW = "sw"  # SW write wins when SW and HW write in the same delta
    HW = "hw"  # HW write wins
