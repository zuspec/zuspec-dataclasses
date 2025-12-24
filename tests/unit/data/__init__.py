"""
RISC-V RV64I Transfer-Function Level Model Package

This package provides a functional model of the RISC-V RV64I base integer
instruction set without timing accuracy.
"""

from .rv64_xf import Rv64XF

__all__ = ['Rv64XF']
