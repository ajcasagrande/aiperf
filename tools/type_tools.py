#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Type checking and stub generation tools for aiperf package.

This script demonstrates how to use various tools for comprehensive type support:
1. mypy - Static type checking
2. stubgen - Generate .pyi stub files
3. pyright - Microsoft's type checker
4. Generate type stubs for dependencies
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and print results."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.stdout:
            print("STDOUT:")
            print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed with return code {result.returncode}")
            return False

    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False


def mypy_check() -> bool:
    """Run mypy type checking."""
    return run_command(["mypy", "aiperf/"], "MyPy type checking")


def generate_stubs() -> bool:
    """Generate .pyi stub files for the package."""
    # Create stubs directory
    stubs_dir = Path("stubs")
    stubs_dir.mkdir(exist_ok=True)

    # Generate stubs for aiperf package
    success = run_command(
        ["stubgen", "-p", "aiperf", "-o", "stubs/"], "Generate stubs for aiperf package"
    )

    if success:
        print(f"\n📁 Stub files generated in: {stubs_dir.absolute()}")

        # List generated files
        for stub_file in stubs_dir.rglob("*.pyi"):
            print(f"  - {stub_file}")

    return success


def generate_dependency_stubs() -> bool:
    """Generate stubs for key dependencies that might not have types."""
    dependencies = [
        "transformers",
        "dask",
        "bokeh",
        "soundfile",
        "setproctitle",
        "ruamel",
        "uvloop",
    ]

    stubs_dir = Path("stubs")
    stubs_dir.mkdir(exist_ok=True)

    success = True
    for dep in dependencies:
        try:
            __import__(dep)
            result = run_command(
                ["stubgen", "-p", dep, "-o", "stubs/"], f"Generate stubs for {dep}"
            )
            success = success and result
        except ImportError:
            print(f"⚠️  Dependency {dep} not installed, skipping stub generation")

    return success


def pyright_check() -> bool:
    """Run pyright type checking (if available)."""
    return run_command(["pyright", "aiperf/"], "Pyright type checking")


def validate_py_typed() -> bool:
    """Validate that py.typed file exists and package is properly configured."""
    py_typed_path = Path("aiperf/py.typed")

    if not py_typed_path.exists():
        print("❌ py.typed file not found!")
        return False

    print("✅ py.typed file exists")

    # Check if package has __init__.py
    init_path = Path("aiperf/__init__.py")
    if not init_path.exists():
        print("❌ __init__.py not found in package root!")
        return False

    print("✅ Package __init__.py exists")

    # Check if package is installable
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import aiperf; print('Package importable')"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print("✅ Package is importable")
            return True
        else:
            print(f"❌ Package import failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error checking package: {e}")
        return False


def main():
    """Main function to run all type checking tools."""
    print("🔍 AIPerf Type Checking and Stub Generation Tools")
    print("=" * 60)

    # Change to project root
    project_root = Path(__file__).parent.parent
    import os

    os.chdir(project_root)

    # Validate setup
    print("\n1. Validating py.typed setup...")
    validate_py_typed()

    # Run type checking
    print("\n2. Running type checkers...")
    mypy_check()
    pyright_check()

    # Generate stubs
    print("\n3. Generating stub files...")
    generate_stubs()
    generate_dependency_stubs()

    print(f"\n{'=' * 60}")
    print("🎉 Type checking and stub generation complete!")
    print(f"{'=' * 60}")

    print("\nNext steps:")
    print("1. Review mypy output and fix any type issues")
    print("2. Check generated stubs in the 'stubs/' directory")
    print("3. Consider adding stubs to your package or uploading to typeshed")
    print("4. Add type checking to your CI/CD pipeline")


if __name__ == "__main__":
    main()
