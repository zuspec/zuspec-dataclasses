"""Registry for IR checkers - enables pluggable validation."""

from typing import Dict, Type, Optional, List
import logging

logger = logging.getLogger(__name__)


class CheckerRegistry:
    """
    Global registry for IR profile checkers.
    
    External packages can register their checkers via:
    - Entry points: setuptools entry_points in pyproject.toml
    - Direct registration: CheckerRegistry.register()
    
    The registry enables automatic discovery and management of validation
    profiles without modifying core code.
    """
    
    _checkers: Dict[str, Type['IRProfileChecker']] = {}
    _profiles: Dict[str, Type['Profile']] = {}  # Profile class registry (optional)
    _discovered: bool = False
    
    @classmethod
    def register(cls,
                 checker_class: Type['IRProfileChecker'],
                 profile_name: str,
                 profile_class: Optional[Type['Profile']] = None) -> None:
        """
        Register an IR checker for a profile.
        
        Args:
            checker_class: The checker implementation class
            profile_name: Unique profile name (e.g., 'Retargetable', 'SPI')
            profile_class: Optional Profile class (for MyPy compatibility)
        
        Example:
            from zuspec.dataclasses.ir_checker import CheckerRegistry
            
            CheckerRegistry.register(
                MyCustomChecker,
                'MyProfile',
                MyProfileClass
            )
        """
        if not hasattr(checker_class, 'PROFILE_NAME'):
            logger.warning(
                f"Checker {checker_class.__name__} should define PROFILE_NAME attribute"
            )
        
        cls._checkers[profile_name] = checker_class
        if profile_class:
            cls._profiles[profile_name] = profile_class
        
        logger.debug(f"Registered checker for profile '{profile_name}': {checker_class.__name__}")
    
    @classmethod
    def get_checker(cls, profile_name: str) -> Optional[Type['IRProfileChecker']]:
        """
        Get the checker class for a profile.
        
        Args:
            profile_name: Profile name to look up
            
        Returns:
            Checker class, or None if not found
        """
        cls.discover_all()
        return cls._checkers.get(profile_name)
    
    @classmethod
    def get_profile(cls, profile_name: str) -> Optional[Type['Profile']]:
        """
        Get the Profile class for a profile name (optional).
        
        Args:
            profile_name: Profile name to look up
            
        Returns:
            Profile class, or None if not registered
        """
        cls.discover_all()
        return cls._profiles.get(profile_name)
    
    @classmethod
    def list_profiles(cls) -> List[str]:
        """List all registered profile names."""
        cls.discover_all()
        return sorted(cls._checkers.keys())
    
    @classmethod
    def list_checkers(cls) -> List[str]:
        """List all registered checker class names."""
        cls.discover_all()
        return [checker.__name__ for checker in cls._checkers.values()]
    
    @classmethod
    def discover_all(cls) -> None:
        """
        Discover both checkers and profiles from entry points.
        
        This creates the association between Profile classes and their
        corresponding IR checker implementations.
        
        Entry points are defined in pyproject.toml:
        
        [project.entry-points."zuspec.ir_checkers"]
        ProfileName = "package.module:CheckerClass"
        
        [project.entry-points."zuspec.profiles"]
        ProfileName = "package.module:ProfileClass"
        """
        if cls._discovered:
            return
        
        try:
            # Try Python 3.10+ API first
            from importlib.metadata import entry_points
        except ImportError:
            try:
                # Fallback to importlib_metadata for Python 3.8-3.9
                from importlib_metadata import entry_points
            except ImportError:
                logger.warning("Cannot discover entry points: importlib.metadata not available")
                cls._discovered = True
                return
        
        # Discover profiles (optional, for MyPy compatibility)
        try:
            profile_eps = cls._get_entry_points('zuspec.profiles')
            for ep in profile_eps:
                try:
                    profile_class = ep.load()
                    cls._profiles[ep.name] = profile_class
                    logger.debug(f"Discovered profile '{ep.name}': {profile_class.__name__}")
                except Exception as e:
                    logger.warning(f"Failed to load profile entry point '{ep.name}': {e}")
        except Exception as e:
            logger.debug(f"No profile entry points found: {e}")
        
        # Discover checkers
        try:
            checker_eps = cls._get_entry_points('zuspec.ir_checkers')
            for ep in checker_eps:
                try:
                    checker_class = ep.load()
                    
                    # Validate that checker has PROFILE_NAME
                    if not hasattr(checker_class, 'PROFILE_NAME'):
                        logger.warning(
                            f"Checker {checker_class.__name__} from entry point '{ep.name}' "
                            f"should define PROFILE_NAME attribute"
                        )
                    
                    # Use entry point name as profile name
                    profile_name = ep.name
                    cls._checkers[profile_name] = checker_class
                    logger.debug(f"Discovered checker '{profile_name}': {checker_class.__name__}")
                    
                except Exception as e:
                    logger.warning(f"Failed to load checker entry point '{ep.name}': {e}")
        except Exception as e:
            logger.debug(f"No checker entry points found: {e}")
        
        cls._discovered = True
    
    @classmethod
    def _get_entry_points(cls, group: str):
        """Get entry points for a group (Python 3.8+ compatible)."""
        try:
            from importlib.metadata import entry_points
        except ImportError:
            from importlib_metadata import entry_points
        
        eps = entry_points()
        
        # Python 3.10+ has select() method
        if hasattr(eps, 'select'):
            return eps.select(group=group)
        # Python 3.8-3.9 returns dict-like
        elif isinstance(eps, dict):
            return eps.get(group, [])
        else:
            # EntryPoints object (Python 3.9)
            return [ep for ep in eps if ep.group == group]
    
    @classmethod
    def reset(cls) -> None:
        """Reset registry (mainly for testing)."""
        cls._checkers.clear()
        cls._profiles.clear()
        cls._discovered = False


# Type hints (avoid circular imports)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .base import IRProfileChecker
    from ..profiles import Profile
