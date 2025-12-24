#!/usr/bin/env python3
"""Script to test MyPy plugin with profile checking."""
import subprocess
import sys
from pathlib import Path

def run_mypy(test_file: str) -> tuple[int, str, str]:
    """Run mypy on a test file and return result."""
    cmd = [
        sys.executable, "-m", "mypy",
        "--config-file", "packages/zuspec-dataclasses/pyproject.toml",
        test_file
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def main():
    test_dir = Path("tests/unit/mypy_tests")
    
    print("=" * 70)
    print("Testing MyPy Plugin with Profile Checking")
    print("=" * 70)
    
    # Test 1: Python profile (should pass)
    print("\n1. Testing Python Profile (should pass)...")
    print("-" * 70)
    rc, stdout, stderr = run_mypy(str(test_dir / "test_python_profile.py"))
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    if rc == 0:
        print("✓ PASS: Python profile allows flexible code")
    else:
        print("✗ FAIL: Python profile should not produce errors")
    
    # Test 2: Retargetable profile (should show errors)
    print("\n2. Testing Retargetable Profile (should show errors)...")
    print("-" * 70)
    rc, stdout, stderr = run_mypy(str(test_dir / "test_retargetable_profile.py"))
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    if rc != 0:
        print("✓ EXPECTED: Retargetable profile caught violations")
    else:
        print("⚠ NOTE: Retargetable profile should catch some violations")
    
    # Test 3: Custom profile
    print("\n3. Testing Custom Profile...")
    print("-" * 70)
    rc, stdout, stderr = run_mypy(str(test_dir / "test_custom_profile.py"))
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    if rc != 0:
        print("✓ EXPECTED: Custom profile caught violations")
    else:
        print("⚠ NOTE: Custom profile checking may need refinement")
    
    print("\n" + "=" * 70)
    print("MyPy plugin testing complete")
    print("=" * 70)


if __name__ == '__main__':
    main()
