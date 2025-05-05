#!/usr/bin/env python3
"""
AIPerf main entry point.

This script provides a command-line interface for running AIPerf benchmarks.
"""

import asyncio
import argparse
import logging
import os
import sys
import time
import yaml
from typing import Dict, Any, Optional

from .component_init import (
    initialize_all_components,
    start_all_components,
    stop_all_components,
    shutdown_all_components,
)
from .config.config_models import AIPerfConfig


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("aiperf.run")


def load_config(config_path: str) -> Optional[AIPerfConfig]:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to configuration file

    Returns:
        AIPerfConfig object or None if loading failed
    """
    try:
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            return None

        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f)

        # Create AIPerfConfig from dictionary
        config = AIPerfConfig.from_dict(config_dict)
        logger.info(
            f"Loaded configuration from {config_path} with profile: {config.profile_name}"
        )
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return None


async def run_aiperf(
    config: AIPerfConfig, run_duration: Optional[float] = None
) -> bool:
    """Run AIPerf with the given configuration.

    Args:
        config: AIPerf configuration
        run_duration: Optional run duration in seconds

    Returns:
        True if run was successful, False otherwise
    """
    start_time = time.time()
    logger.info(f"Starting AIPerf with profile: {config.profile_name}")

    components = None
    try:
        # Initialize all components
        components = await initialize_all_components(config)
        logger.info("All components initialized successfully")

        # Start the benchmark
        success = await start_all_components(components)
        if not success:
            logger.error("Failed to start benchmark")
            return False

        logger.info(f"Benchmark started successfully")

        # Run for specified duration if provided
        if run_duration is not None:
            logger.info(f"Running benchmark for {run_duration} seconds")
            await asyncio.sleep(run_duration)

            # Stop the benchmark
            logger.info("Stopping benchmark")
            await stop_all_components(components)
        else:
            # Run until interrupted
            logger.info("Benchmark running. Press Ctrl+C to stop...")

            # Set up signal handlers for graceful shutdown
            import signal

            loop = asyncio.get_running_loop()
            stop_event = asyncio.Event()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            # Wait for stop signal
            await stop_event.wait()

            # Stop the benchmark
            logger.info("Stopping benchmark")
            await stop_all_components(components)

        elapsed = time.time() - start_time
        logger.info(f"Benchmark completed in {elapsed:.2f} seconds")

        # Collect and show summary statistics
        records_manager = components.get("records_manager")
        if records_manager:
            metrics = await records_manager.get_metrics()
            logger.info("Benchmark results:")
            for key, value in metrics.items():
                logger.info(f"  {key}: {value}")

        return True
    except Exception as e:
        logger.error(f"Error running benchmark: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Clean up resources
        if components:
            await shutdown_all_components(components)
            logger.info("All components shut down")


def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Run AIPerf benchmarks")

    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to configuration file",
    )

    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        help="Run duration in seconds",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main():
    """Main entry point for AIPerf."""
    # Parse command-line arguments
    args = parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger("aiperf").setLevel(logging.DEBUG)

    # Load configuration
    config = load_config(args.config)
    if not config:
        sys.exit(1)

    # Run AIPerf
    try:
        success = asyncio.run(run_aiperf(config, args.duration))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
