"""Python profile IR checker - permissive checking for pure Python code."""

from typing import List
from .base import BaseIRChecker, CheckError, CheckContext
import logging

logger = logging.getLogger(__name__)


class PythonIRChecker(BaseIRChecker):
    """
    IR-based checker for Python profile.
    
    This is a permissive profile that allows all Python constructs:
    - Infinite-width integers
    - Dynamic attribute access (hasattr, getattr, etc.)
    - Unannotated variables
    - Any/object types
    - Non-Zuspec types
    
    Use this profile for pure Python implementations that won't be compiled
    to hardware or other targets.
    
    This checker performs minimal validation - mostly structural checks.
    """
    
    PROFILE_NAME = 'Python'
    
    def check_field(self, field: 'Field', check_ctx: CheckContext) -> List[CheckError]:
        """Python profile: no field restrictions."""
        return []
    
    def check_function(self, func: 'Function', check_ctx: CheckContext) -> List[CheckError]:
        """Python profile: no function restrictions, but still check body structure."""
        # We still traverse the body to catch obvious errors
        # but don't enforce type restrictions
        return super().check_function(func, check_ctx)
    
    def check_statement(self, stmt: 'Stmt', check_ctx: CheckContext) -> List[CheckError]:
        """Python profile: no statement restrictions."""
        # Still recurse to check structure
        return super().check_statement(stmt, check_ctx)
    
    def check_expression(self, expr: 'Expr', check_ctx: CheckContext) -> List[CheckError]:
        """Python profile: no expression restrictions."""
        # Still recurse to check structure
        return super().check_expression(expr, check_ctx)


# Type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..ir import Field, Function, Stmt, Expr
