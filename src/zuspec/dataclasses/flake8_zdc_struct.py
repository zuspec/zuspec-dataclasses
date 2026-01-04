"""
Flake8 plugin for Zuspec validation.

This plugin integrates the IR-based checker framework with flake8,
enabling automatic validation of Zuspec code as part of the normal
flake8 workflow.

Configuration via .flake8, setup.cfg, or pyproject.toml:

    [flake8]
    zuspec-profile = Retargetable
    zuspec-enabled = True

The plugin automatically discovers all registered profiles via entry points.
"""

import ast
import sys
import importlib.util
from pathlib import Path
from typing import Generator, Tuple, Any, List, Optional, Type
import logging

logger = logging.getLogger(__name__)


class ZuspecFlake8Plugin:
    """
    Flake8 plugin for Zuspec retargetable code validation.
    
    This plugin:
    1. Checks if a file uses Zuspec
    2. Dynamically loads and converts Python classes to IR
    3. Runs the appropriate profile checker
    4. Reports errors in flake8 format
    """
    
    name = 'zuspec'
    version = '1.0.0'
    
    # Class-level configuration (set by flake8)
    zuspec_profile = 'Retargetable'
    zuspec_enabled = True
    
    def __init__(self, tree: ast.AST, filename: str = '<unknown>', lines: Optional[List[str]] = None):
        """
        Initialize plugin.
        
        Args:
            tree: Python AST of the file
            filename: Path to the file being checked
            lines: Source lines (optional, for better error reporting)
        """
        self.tree = tree
        self.filename = filename
        self.lines = lines or []
        
        # Track what we added to sys.path and sys.modules for cleanup
        self._added_to_path = None
        self._added_module_name = None
        self._old_module = None
    
    @classmethod
    def add_options(cls, option_manager):
        """Add plugin-specific configuration options to flake8."""
        option_manager.add_option(
            '--zuspec-profile',
            default='Retargetable',
            parse_from_config=True,
            help='Zuspec profile to use for validation (default: Retargetable)'
        )
        option_manager.add_option(
            '--zuspec-enabled',
            default=True,
            parse_from_config=True,
            action='store_true',
            help='Enable Zuspec checking (default: True)'
        )
    
    @classmethod
    def parse_options(cls, options):
        """Parse options provided by flake8."""
        cls.zuspec_profile = getattr(options, 'zuspec_profile', 'Retargetable')
        cls.zuspec_enabled = getattr(options, 'zuspec_enabled', True)
    
    def run(self) -> Generator[Tuple[int, int, str, type], None, None]:
        """
        Main entry point called by flake8.
        
        Yields:
            Tuples of (line, col, message, type) for each error found
        """
        # Skip if disabled
        if not self.zuspec_enabled:
            return
        
        # Quick check: does this file import zuspec?
        if not self._has_zuspec_imports():
            return
        
        # Try to extract and check Zuspec classes
        try:
            errors = self._check_file()
            for error in errors:
                message = f"{error.code} {error.message}"
                yield (error.lineno, error.col_offset, message, type(self))
        except Exception as e:
            # Report plugin error
            logger.error(f"Error in Zuspec flake8 plugin: {e}", exc_info=True)
            yield (1, 0, f"ZDC999 Internal error: {e}", type(self))
    
    def _has_zuspec_imports(self) -> bool:
        """Quick check if file imports zuspec."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and 'zuspec' in node.module:
                    return True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if 'zuspec' in alias.name:
                        return True
        return False
    
    def _check_file(self) -> List['CheckError']:
        """Extract classes and run IR checker."""
        from .ir_checker import ZuspecIRChecker
        from .data_model_factory import DataModelFactory
        
        # Extract Zuspec classes from the file
        classes = self._extract_zuspec_classes()
        
        if not classes:
            return []
        
        # NOTE: After _extract_zuspec_classes(), the module is still in sys.modules
        # and sys.path still has the package root. This is intentional so that
        # DataModelFactory can use inspect.getsource() on the classes.
        # We'll clean up after checking is complete.
        
        # Try to check via IR (full validation)
        all_errors = []
        
        # Group classes by profile
        profile_groups = {}
        for cls in classes:
            profile_name = self._detect_profile(cls)
            if profile_name not in profile_groups:
                profile_groups[profile_name] = []
            profile_groups[profile_name].append(cls)
        
        # Check each profile group
        for profile_name, profile_classes in profile_groups.items():
            try:
                # Build IR for this group
                factory = DataModelFactory()
                profile_context = factory.build(profile_classes)
                
                # Check with detected profile
                checker = ZuspecIRChecker(profile=profile_name)
                errors = checker.check_context(profile_context)
                all_errors.extend(errors)
                
            except Exception as e:
                # IR building failed - fall back to basic field checking
                logger.debug(f"IR build failed for profile '{profile_name}': {e}")
                
                # Do basic field checking directly on Python classes
                for cls in profile_classes:
                    fallback_errors = self._check_fields_fallback(cls, profile_name)
                    all_errors.extend(fallback_errors)
        
        # Clean up: remove module and package root from sys.modules and sys.path
        self._cleanup_import()
        
        return all_errors
    
    def _detect_profile(self, cls: type) -> str:
        """
        Detect the profile for a class from its __profile__ attribute.
        
        The profile is set by the @dataclass(profile=...) decorator.
        If not specified, returns the configured default (usually 'Retargetable').
        
        Args:
            cls: Class to detect profile for
            
        Returns:
            Profile name as string (e.g., 'Retargetable', 'Python')
        """
        # Check if class has __profile__ attribute set by decorator
        if hasattr(cls, '__profile__'):
            profile_cls = cls.__profile__
            
            # Extract profile name using get_name() method if available
            if hasattr(profile_cls, 'get_name'):
                try:
                    return profile_cls.get_name()
                except Exception as e:
                    logger.warning(f"Failed to get profile name from {profile_cls}: {e}")
            
            # Try __name__ attribute and strip 'Profile' suffix
            if hasattr(profile_cls, '__name__'):
                profile_name = profile_cls.__name__
                # Remove 'Profile' suffix if present (e.g., 'RetargetableProfile' -> 'Retargetable')
                if profile_name.endswith('Profile'):
                    profile_name = profile_name[:-7]  # len('Profile') = 7
                    if profile_name:  # Ensure we didn't remove everything
                        return profile_name
                return profile_name  # Return as-is if no suffix or suffix removal left empty string
            
            # Fallback to string representation
            profile_str = str(profile_cls)
            if 'Retargetable' in profile_str:
                return 'Retargetable'
            elif 'Python' in profile_str:
                return 'Python'
        
        # No profile specified - use configured default
        return self.zuspec_profile
    
    def _check_fields_fallback(self, cls: type, profile_name: str) -> List['CheckError']:
        """
        Fallback field checker when IR building fails.
        
        This directly inspects Python dataclass fields and performs
        basic type checking without full IR analysis.
        
        Args:
            cls: Class to check
            profile_name: Profile name for this class
            
        Returns:
            List of errors found
        """
        from .ir_checker.base import CheckError
        import inspect
        
        errors = []
        
        # Only check Retargetable profile (Python profile is permissive)
        if profile_name != 'Retargetable':
            return errors
        
        # Get source file and line numbers if possible
        try:
            source_file = inspect.getsourcefile(cls)
            source_lines, start_line = inspect.getsourcelines(cls)
        except (TypeError, OSError):
            source_file = self.filename
            start_line = 1
            source_lines = []
        
        # Check dataclass fields
        if hasattr(cls, '__dataclass_fields__'):
            for field_name, field_info in cls.__dataclass_fields__.items():
                # Skip private/internal fields
                if field_name.startswith('_impl') or field_name == 'xtor_if':
                    continue
                
                # Get field type annotation
                field_type = field_info.type
                
                # Check if it's a Zuspec type
                if not self._is_zuspec_type_annotation(field_type):
                    # Try to find line number for this field
                    field_line = start_line
                    for i, line in enumerate(source_lines):
                        if field_name in line and ':' in line:
                            field_line = start_line + i
                            break
                    
                    errors.append(CheckError(
                        code='ZDC002',
                        message=f"Field '{field_name}' has non-Zuspec type '{self._type_name(field_type)}'. "
                                f"Retargetable code requires Zuspec types",
                        filename=source_file or self.filename,
                        lineno=field_line,
                        col_offset=4  # Typical indentation
                    ))
        
        return errors
    
    def _is_zuspec_type_annotation(self, type_annotation) -> bool:
        """
        Check if a type annotation is a Zuspec type.
        
        Args:
            type_annotation: Python type annotation
            
        Returns:
            True if it's a Zuspec type
        """
        import typing
        
        # Handle typing.Annotated (used by zdc.u32, zdc.bit, etc.)
        if hasattr(typing, 'get_origin') and hasattr(typing, 'get_args'):
            origin = typing.get_origin(type_annotation)
            if origin is typing.Annotated:
                # Get the actual type from Annotated[ActualType, ...]
                args = typing.get_args(type_annotation)
                if args:
                    type_annotation = args[0]
        
        # Get the type's module
        type_module = getattr(type_annotation, '__module__', '')
        
        # Check if it's from zuspec modules
        if 'zuspec' in type_module:
            return True
        
        # Check type name
        type_name = getattr(type_annotation, '__name__', str(type_annotation))
        
        # Known Zuspec type prefixes
        zuspec_prefixes = ('uint', 'int', 'u', 'i', 'bit', 'bv', 'bitv')
        if any(type_name.startswith(prefix) for prefix in zuspec_prefixes):
            return True
        
        # Check for Zuspec base classes
        try:
            if hasattr(type_annotation, '__mro__'):
                for base in type_annotation.__mro__:
                    base_module = getattr(base, '__module__', '')
                    if 'zuspec' in base_module:
                        return True
        except Exception:
            pass
        
        return False
    
    def _type_name(self, type_annotation) -> str:
        """Get a readable name for a type annotation."""
        if hasattr(type_annotation, '__name__'):
            return type_annotation.__name__
        return str(type_annotation)
    
    def _extract_zuspec_classes(self) -> List[type]:
        """
        Extract Zuspec dataclass classes from the file.
        
        Strategy:
        1. Try to dynamically import the module
        2. Find all classes with __dataclass_fields__
        3. Return class objects for IR conversion
        """
        # Try import-based approach
        try:
            classes = self._extract_via_import()
            if classes:
                return classes
        except Exception as e:
            logger.debug(f"Import-based extraction failed for {self.filename}: {e}")
        
        # Fallback: no classes (AST-only extraction is too limited)
        return []
    
    def _extract_via_import(self) -> List[type]:
        """Dynamically import module and extract decorated classes."""
        filepath = Path(self.filename).resolve()
        
        # Skip if not a real file
        if not filepath.exists():
            return []
        
        # Find package root (directory containing the top-level package)
        package_root = self._find_package_root(filepath)
        if not package_root:
            # Not in a package - use parent directory
            package_root = filepath.parent
        
        # Calculate full module name
        module_name = self._get_module_name(filepath, package_root)
        
        # Add package root to sys.path (not immediate parent!)
        path_added = False
        package_root_str = str(package_root)
        if package_root_str not in sys.path:
            sys.path.insert(0, package_root_str)
            path_added = True
        
        try:
            # Load module with full package name
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if not spec or not spec.loader:
                return []
            
            module = importlib.util.module_from_spec(spec)
            
            # Temporarily add to sys.modules with full name
            old_module = sys.modules.get(module_name)
            sys.modules[module_name] = module
            
            try:
                spec.loader.exec_module(module)
                
                # Find decorated classes
                classes = []
                for name in dir(module):
                    if name.startswith('_'):
                        continue
                    
                    try:
                        obj = getattr(module, name)
                        if isinstance(obj, type):
                            # Check if it's a dataclass
                            if hasattr(obj, '__dataclass_fields__'):
                                # Check if it's from this module (use full name)
                                if hasattr(obj, '__module__') and obj.__module__ == module_name:
                                    classes.append(obj)
                    except Exception as e:
                        logger.debug(f"Error inspecting {name}: {e}")
                        continue
                
                # Store cleanup info - DON'T clean up yet!
                # We need the module to stay in sys.modules for inspect.getsource()
                self._added_to_path = package_root_str if path_added else None
                self._added_module_name = module_name
                self._old_module = old_module
                
                return classes
            except Exception as e:
                # If exec_module fails, clean up immediately
                if old_module is not None:
                    sys.modules[module_name] = old_module
                elif module_name in sys.modules:
                    del sys.modules[module_name]
                raise
        
        except Exception as e:
            # If anything fails, clean up sys.path
            if path_added and package_root_str in sys.path:
                sys.path.remove(package_root_str)
            raise
    
    def _cleanup_import(self):
        """Clean up sys.modules and sys.path after checking is complete."""
        # Restore sys.modules
        if self._added_module_name:
            if self._old_module is not None:
                sys.modules[self._added_module_name] = self._old_module
            elif self._added_module_name in sys.modules:
                del sys.modules[self._added_module_name]
        
        # Clean up sys.path
        if self._added_to_path and self._added_to_path in sys.path:
            sys.path.remove(self._added_to_path)
    
    def _find_package_root(self, filepath: Path) -> Optional[Path]:
        """
        Find the package root for a Python file.
        
        Walks up the directory tree until finding a directory without __init__.py.
        That's the package root that should be in sys.path.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            Package root directory (parent of top-level package),
            or None if not in a package
        """
        current = filepath.parent
        last_package_parent = None
        
        # Walk up until we find a dir without __init__.py
        while current != current.parent:  # Not at filesystem root
            if (current / '__init__.py').exists():
                # This is a package directory
                last_package_parent = current.parent
                current = current.parent
            else:
                # This directory is not a package
                # The last package's parent is the root
                break
        
        return last_package_parent if last_package_parent else current
    
    def _get_module_name(self, filepath: Path, package_root: Path) -> str:
        """
        Calculate the full module name from filepath and package root.
        
        Args:
            filepath: Path to Python file
            package_root: Package root directory
            
        Returns:
            Full module name (e.g., 'org.featherweight_vip.fwvip_wb.initiator')
        """
        try:
            # Get relative path from package root
            rel_path = filepath.relative_to(package_root)
            
            # Convert path to module name: remove .py, replace / with .
            module_parts = list(rel_path.parts[:-1])  # All directories
            module_parts.append(rel_path.stem)        # Filename without .py
            
            return '.'.join(module_parts)
        except ValueError:
            # filepath not relative to package_root - just use stem
            return filepath.stem


def plugin_factory():
    """Entry point for flake8 plugin registration."""
    return ZuspecFlake8Plugin


# For backward compatibility, also export the class directly
# Some flake8 versions expect the class, not a factory
__all__ = ['ZuspecFlake8Plugin', 'plugin_factory']
