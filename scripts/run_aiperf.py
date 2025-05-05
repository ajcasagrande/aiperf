#!/usr/bin/env python
"""
AIPerf Runner Script

This script provides a convenient way to run AIPerf benchmarks with custom configurations.
It can automatically create configuration files with your API keys and other customizations.
"""

import argparse
import os
import sys
import yaml
import shutil
from pathlib import Path


def setup_config(config_path, output_path, api_key=None, rate=None, duration=None):
    """Set up a configuration file with customized parameters.

    Args:
        config_path: Path to the template configuration file
        output_path: Path to write the customized configuration
        api_key: API key to use (if applicable)
        rate: Request rate (requests per second)
        duration: Test duration in seconds

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Read the template configuration
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Update the configuration with custom parameters
        if api_key:
            # Update the API key for all endpoints
            for endpoint in config.get("endpoints", []):
                if "auth" in endpoint and "api_key" in endpoint["auth"]:
                    endpoint["auth"]["api_key"] = api_key

        if rate is not None:
            # Update the request rate
            if "timing" in config and "parameters" in config["timing"]:
                config["timing"]["parameters"]["rate"] = rate

        if duration is not None:
            # Update the test duration
            if "timing" in config:
                config["timing"]["duration"] = duration

        # Write the customized configuration
        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"Created custom configuration at: {output_path}")
        return True

    except Exception as e:
        print(f"Error creating configuration: {e}")
        return False


def run_benchmark(config_path, log_level="INFO"):
    """Run the AIPerf benchmark with the given configuration.

    Args:
        config_path: Path to the configuration file
        log_level: Logging level

    Returns:
        int: Return code from the benchmark
    """
    try:
        # Add the project root to Python path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        # Import the aiperf CLI
        from aiperf.cli.aiperf_cli import main_async
        import asyncio

        # Set up the arguments
        sys.argv = [sys.argv[0], "run", config_path, "--log-level", log_level]

        # Run the benchmark
        return asyncio.run(main_async())

    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
        return 1
    except Exception as e:
        print(f"Error running benchmark: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AIPerf Runner Script")
    parser.add_argument(
        "--config",
        default="aiperf/config/examples/openai_example.yaml",
        help="Path to template configuration file",
    )
    parser.add_argument(
        "--output",
        default="custom_configs/my_config.yaml",
        help="Path to write customized configuration",
    )
    parser.add_argument("--api-key", help="API key to use (if applicable)")
    parser.add_argument("--rate", type=float, help="Request rate (requests per second)")
    parser.add_argument("--duration", type=int, help="Test duration in seconds")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only set up the configuration, don't run the benchmark",
    )

    args = parser.parse_args()

    # Set up the configuration
    if not os.path.exists(args.config):
        print(f"Error: Configuration template not found: {args.config}")
        return 1

    if not setup_config(
        args.config, args.output, args.api_key, args.rate, args.duration
    ):
        return 1

    # Run the benchmark if not in setup-only mode
    if not args.setup_only:
        return run_benchmark(args.output, args.log_level)

    return 0


if __name__ == "__main__":
    sys.exit(main())
