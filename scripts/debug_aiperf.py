#!/usr/bin/env python
"""
AIPerf Debugging Script

This script provides a focused way to debug the AIPerf system with better
visibility into component initialization and execution.
"""

import argparse
import asyncio
import importlib
import os
import sys
import yaml
from pathlib import Path


async def debug_aiperf_system(config_path, log_level="DEBUG"):
    """Run AIPerf with explicit component initialization for easier debugging.

    This function explicitly imports and initializes key AIPerf components
    to make it easier to set breakpoints and inspect the system's behavior.

    Args:
        config_path: Path to the configuration file
        log_level: Logging level to use

    Returns:
        int: Return code from the benchmark
    """
    try:
        # Add the project root to Python path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        # Explicitly import AIPerf components for debugging
        from aiperf.config.config_loader import ConfigLoader
        from aiperf.system.system_controller import SystemController
        from aiperf.util.logging_util import setup_logging

        # Set up logging
        setup_logging(log_level=log_level)

        # Load the configuration
        print(f"Debug: Loading configuration from: {config_path}")
        config = ConfigLoader.load_from_file(config_path)

        # Create the system controller
        print(
            f"Debug: Initializing system controller for profile: {config.profile_name}"
        )
        controller = SystemController(config)

        # Initialize and start - GOOD BREAKPOINT LOCATIONS
        if not await controller.initialize():
            print("Debug: Failed to initialize system controller")
            return 1

        # Wait for all components to be ready
        if not await controller.ready_check():
            print("Debug: System is not ready")
            return 1

        # Start profile - GOOD BREAKPOINT LOCATION
        if not await controller.start_profile():
            print("Debug: Failed to start profile")
            return 1

        try:
            # Wait for shutdown (e.g., CTRL+C)
            print("Debug: Running profile, press CTRL+C to stop")
            await controller.wait_for_shutdown()
        except KeyboardInterrupt:
            print("Debug: Keyboard interrupt detected, shutting down...")
        finally:
            # Ensure we shutdown - GOOD BREAKPOINT LOCATION
            await controller.shutdown()

        return 0

    except Exception as e:
        print(f"Debug Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AIPerf Debug Script")
    parser.add_argument("--config", required=True, help="Path to configuration file")
    parser.add_argument(
        "--log-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Set up the configuration
    if not os.path.exists(args.config):
        print(f"Error: Configuration not found: {args.config}")
        return 1

    # Run the AIPerf system with explicit debug points
    return asyncio.run(debug_aiperf_system(args.config, args.log_level))


if __name__ == "__main__":
    sys.exit(main())
