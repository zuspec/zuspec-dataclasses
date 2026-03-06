"""
Functional coverage support for zuspec-dataclasses.
"""
from .base import Covergroup, CoverpointInstance, CrossInstance
from .descriptors import coverpoint, cross
from .bins import binsof, cross_bins, cross_ignore, cross_illegal

__all__ = [
    'Covergroup',
    'CoverpointInstance',
    'CrossInstance',
    'coverpoint',
    'cross',
    'binsof',
    'cross_bins',
    'cross_ignore',
    'cross_illegal',
]
