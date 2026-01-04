"""Main orchestrator for IR checking."""

from typing import Optional, List
from .base import CheckError, CheckContext
from .registry import CheckerRegistry
import logging

logger = logging.getLogger(__name__)


class ZuspecIRChecker:
    """
    Main orchestrator for IR checking.
    
    This class:
    1. Looks up the appropriate checker for a profile
    2. Delegates to that checker
    3. Provides a consistent API for all tools (flake8, CLI, etc.)
    
    Usage:
        from zuspec.dataclasses.ir_checker import ZuspecIRChecker
        from zuspec.dataclasses.data_model_factory import DataModelFactory
        
        # Build IR from classes
        factory = DataModelFactory()
        context = factory.build([MyClass])
        
        # Check with a profile
        checker = ZuspecIRChecker(profile='Retargetable')
        errors = checker.check_context(context)
        
        # Report errors
        for error in errors:
            print(f"{error.filename}:{error.lineno}: {error.code}: {error.message}")
    """
    
    def __init__(self, profile: Optional[str] = None):
        """
        Initialize checker with a profile.
        
        Args:
            profile: Profile name ('Retargetable', 'Python', or custom)
                    Defaults to 'Retargetable' if not specified.
        
        Raises:
            ValueError: If profile is not registered
        """
        self.profile = profile or 'Retargetable'
        
        # Ensure entry points are discovered
        CheckerRegistry.discover_all()
        
        # Get checker for profile
        checker_class = CheckerRegistry.get_checker(self.profile)
        if checker_class is None:
            available = CheckerRegistry.list_profiles()
            raise ValueError(
                f"No checker registered for profile '{self.profile}'. "
                f"Available profiles: {', '.join(available) if available else 'none'}"
            )
        
        # Instantiate checker
        try:
            self.checker = checker_class()
            logger.debug(f"Initialized checker for profile '{self.profile}': {checker_class.__name__}")
        except Exception as e:
            raise ValueError(f"Failed to instantiate checker for profile '{self.profile}': {e}")
    
    def check_context(self, context: 'Context') -> List[CheckError]:
        """
        Main entry point: analyze an IR Context and return errors.
        
        Args:
            context: IR Context containing all type definitions (from DataModelFactory)
            
        Returns:
            List of validation errors found, sorted by location
        """
        from ..ir import Context as IRContext
        
        if context is None:
            logger.warning("Received None context, returning no errors")
            return []
        
        # Create check context
        check_ctx = CheckContext()
        
        # Run checker
        try:
            errors = self.checker.check_context(context, check_ctx)
            
            # Sort errors by location for consistent output
            errors.sort(key=lambda e: (e.filename, e.lineno, e.col_offset))
            
            logger.debug(f"Profile '{self.profile}' found {len(errors)} errors")
            return errors
            
        except Exception as e:
            logger.error(f"Error during checking with profile '{self.profile}': {e}", exc_info=True)
            # Return a single error indicating the failure
            return [CheckError(
                code='ZDC999',
                message=f"Internal checker error: {e}",
                filename='',
                lineno=1,
                col_offset=0,
                severity='error'
            )]
    
    @staticmethod
    def list_available_profiles() -> List[str]:
        """
        List all available profiles.
        
        Returns:
            Sorted list of profile names
        """
        CheckerRegistry.discover_all()
        return CheckerRegistry.list_profiles()


# Type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..ir import Context
