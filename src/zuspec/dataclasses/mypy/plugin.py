"""
DEPRECATED: MyPy plugin for Zuspec validation.

This MyPy plugin is deprecated as of version 0.0.2.
Please use the flake8 plugin instead, which provides the same validation
functionality through the IR-based checker framework.

Migration:
1. Remove mypy plugin from pyproject.toml:
   # OLD:
   # [tool.mypy]
   # plugins = ["zuspec.dataclasses.mypy.plugin"]
   
2. Use flake8 for validation:
   $ flake8 your_file.py
   
3. Configure profile in .flake8:
   [flake8]
   zuspec-profile = Retargetable

The IR-based checker provides:
- Same validation rules as the MyPy plugin
- Better error messages with precise locations
- Extensibility for custom profiles
- Independence from MyPy's release cycle
- Works with multiple tools (flake8, CLI, future integrations)

This plugin file is kept for backward compatibility but will be removed
in a future version.
"""

import warnings
from typing import Type

# Show deprecation warning when plugin is loaded
warnings.warn(
    "The zuspec.dataclasses.mypy plugin is deprecated. "
    "Please use the flake8 plugin instead: flake8 your_file.py",
    DeprecationWarning,
    stacklevel=2
)


def plugin(version: str) -> Type['Plugin']:
    """
    MyPy plugin entry point (deprecated).
    
    Returns a no-op plugin that warns about deprecation.
    """
    from mypy.plugin import Plugin
    
    class DeprecatedZuspecPlugin(Plugin):
        """Deprecated plugin that does nothing."""
        
        def __init__(self, options):
            super().__init__(options)
            # Print warning once per mypy run
            if not hasattr(DeprecatedZuspecPlugin, '_warned'):
                print("\n" + "="*70)
                print("WARNING: Zuspec MyPy plugin is DEPRECATED")
                print("="*70)
                print("Please use the flake8 plugin instead:")
                print("  1. Remove 'plugins = [\"zuspec.dataclasses.mypy.plugin\"]' from pyproject.toml")
                print("  2. Run: flake8 your_file.py")
                print("  3. Configure: [flake8] zuspec-profile = Retargetable")
                print("="*70 + "\n")
                DeprecatedZuspecPlugin._warned = True
    
    return DeprecatedZuspecPlugin
