"""
IR-based checker framework for Zuspec.

This module provides a flake8-compatible checker that validates Zuspec code
by analyzing the IR (Intermediate Representation).

Key components:
- BaseIRChecker: Base class for implementing checkers
- IRProfileChecker: Protocol for checker implementations
- CheckerRegistry: Registry for discovering and managing checkers
- ZuspecIRChecker: Main orchestrator
- CheckError, CheckContext: Supporting data structures

External packages can extend by:
1. Implementing IRProfileChecker or subclassing BaseIRChecker
2. Registering via entry points in pyproject.toml:
   
   [project.entry-points."zuspec.ir_checkers"]
   MyProfile = "mypackage.checker:MyChecker"

The checker framework replaces the deprecated MyPy plugin with a more
flexible, tool-independent approach.
"""

from .base import (
    IRProfileChecker,
    BaseIRChecker,
    CheckError,
    CheckContext
)
from .registry import CheckerRegistry
from .checker import ZuspecIRChecker

# Import built-in checkers to ensure they're available
from .retargetable import RetargetableIRChecker
from .python_profile import PythonIRChecker

# Register built-in checkers
CheckerRegistry.register(RetargetableIRChecker, 'Retargetable')
CheckerRegistry.register(PythonIRChecker, 'Python')

__all__ = [
    # Core protocol and base class
    'IRProfileChecker',
    'BaseIRChecker',
    
    # Data structures
    'CheckError',
    'CheckContext',
    
    # Registry and main checker
    'CheckerRegistry',
    'ZuspecIRChecker',
    
    # Built-in implementations
    'RetargetableIRChecker',
    'PythonIRChecker',
]

# Auto-discover entry points after module import
CheckerRegistry.discover_all()
