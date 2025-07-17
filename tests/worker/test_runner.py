#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Test runner for worker tests.

This script provides a convenient way to run all worker tests with various options.
"""

import argparse
import sys
from pathlib import Path

import pytest


def run_tests(args):
    """Run worker tests with specified arguments."""
    test_dir = Path(__file__).parent

    # Build pytest arguments
    pytest_args = [str(test_dir)]

    if args.verbose:
        pytest_args.extend(["-v", "-s"])

    if args.coverage:
        pytest_args.extend(
            [
                "--cov=aiperf.services.worker",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    if args.markers:
        pytest_args.extend(["-m", args.markers])

    if args.test_pattern:
        pytest_args.extend(["-k", args.test_pattern])

    if args.parallel:
        pytest_args.extend(["-n", str(args.parallel)])

    if args.fail_fast:
        pytest_args.append("-x")

    # Run pytest
    return pytest.main(pytest_args)


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run worker service tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py                          # Run all tests
  python test_runner.py --verbose                # Run with verbose output
  python test_runner.py --coverage               # Run with coverage report
  python test_runner.py -k "test_worker_init"    # Run specific test pattern
  python test_runner.py -m "asyncio"             # Run only async tests
  python test_runner.py --parallel 4             # Run tests in parallel
        """,
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Run tests with verbose output"
    )

    parser.add_argument(
        "--coverage", action="store_true", help="Run tests with coverage report"
    )

    parser.add_argument(
        "-m",
        "--markers",
        type=str,
        help="Run tests with specific markers (e.g., 'asyncio')",
    )

    parser.add_argument(
        "-k",
        "--test-pattern",
        type=str,
        help="Run tests matching pattern (e.g., 'test_worker_init')",
    )

    parser.add_argument(
        "-n",
        "--parallel",
        type=int,
        help="Run tests in parallel (requires pytest-xdist)",
    )

    parser.add_argument(
        "-x", "--fail-fast", action="store_true", help="Stop on first failure"
    )

    args = parser.parse_args()

    # Run tests
    exit_code = run_tests(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
