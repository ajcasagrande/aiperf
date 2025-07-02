#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
ZMQ Proxy Test Runner

This script provides convenient commands for running the ZMQ proxy test suite
with different test categories and configurations.

Usage:
    python test_runner.py --help
    python test_runner.py --unit
    python test_runner.py --integration
    python test_runner.py --performance
    python test_runner.py --all
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_pytest(args: list[str]) -> int:
    """Run pytest with the given arguments."""
    cmd = ["python", "-m", "pytest"] + args
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=Path(__file__).parent).returncode


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Run ZMQ Proxy tests with different configurations"
    )

    # Test categories
    parser.add_argument(
        "--unit", action="store_true", help="Run unit tests (fast, mocked)"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests (slower, real ZMQ sockets)",
    )
    parser.add_argument(
        "--performance", action="store_true", help="Run performance tests"
    )
    parser.add_argument("--load", action="store_true", help="Run load tests")
    parser.add_argument("--stress", action="store_true", help="Run stress tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    # Test configuration
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--parallel",
        "-n",
        type=int,
        default=1,
        help="Number of parallel test processes",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Run with coverage reporting"
    )
    parser.add_argument("--profile", action="store_true", help="Run with profiling")

    args = parser.parse_args()

    # Build pytest arguments
    pytest_args = []

    # Add test files
    if args.unit or args.all:
        pytest_args.extend(
            [
                "test_zmq_proxies.py::TestZMQProxyConfiguration",
                "test_zmq_proxies.py::TestZMQProxyFactory",
                "test_zmq_proxies.py::TestZMQProxyLifecycle",
                "test_zmq_proxies.py::TestZMQProxySocketTypes",
                "test_zmq_proxies.py::TestZMQProxyErrorHandling",
            ]
        )

    if args.integration or args.all:
        pytest_args.extend(
            [
                "-m",
                "integration",
                "test_zmq_proxies.py::TestZMQProxyIntegration",
            ]
        )

    if args.performance or args.all:
        pytest_args.extend(
            [
                "-m",
                "performance",
                "test_zmq_proxy_performance.py::TestZMQProxyPerformance",
            ]
        )

    if args.load or args.all:
        pytest_args.extend(
            [
                "-m",
                "load",
                "test_zmq_proxy_performance.py::TestZMQProxyLoad",
            ]
        )

    if args.stress or args.all:
        pytest_args.extend(
            [
                "-m",
                "stress",
                "test_zmq_proxy_performance.py::TestZMQProxyStress",
            ]
        )

    # If no specific tests selected, run unit tests by default
    if not any(
        [
            args.unit,
            args.integration,
            args.performance,
            args.load,
            args.stress,
            args.all,
        ]
    ):
        print("No test category specified. Running unit tests by default.")
        pytest_args = [
            "test_zmq_proxies.py",
            "-m",
            "not integration and not performance and not load and not stress",
        ]

    # Add configuration options
    if args.verbose:
        pytest_args.append("-v")

    if args.parallel > 1:
        pytest_args.extend(["-n", str(args.parallel)])

    if args.coverage:
        pytest_args.extend(
            [
                "--cov=aiperf.common.comms.zmq",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    if args.profile:
        pytest_args.append("--profile")

    # Run the tests
    return run_pytest(pytest_args)


if __name__ == "__main__":
    sys.exit(main())
