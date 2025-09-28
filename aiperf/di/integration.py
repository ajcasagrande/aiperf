# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration layer to wire the DI system into AIPerf."""

import sys
from pathlib import Path

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.di.containers import app_container
from aiperf.di.configuration import auto_load_config

logger = AIPerfLogger(__name__)


def initialize_di_system() -> None:
    """Initialize the dependency injection system."""
    try:
        # Load configuration
        config = auto_load_config()
        logger.info("DI configuration loaded successfully")

        # Configure the application container
        app_container.configure_from_dict(config.model_dump())

        # Wire the container to enable automatic injection
        if config.enable_wiring:
            try:
                app_container.wire(modules=app_container.wiring_config.modules)
                logger.info("DI container wired successfully")
            except Exception as e:
                logger.warning(f"Failed to wire DI container: {e}")

        # Set up logging level if specified
        if config.debug_mode:
            import logging
            logging.getLogger("aiperf.di").setLevel(logging.DEBUG)

        logger.info("Dependency injection system initialized")

    except Exception as e:
        logger.error(f"Failed to initialize DI system: {e}")
        raise


def shutdown_di_system() -> None:
    """Shutdown the dependency injection system."""
    try:
        # Unwire the container
        app_container.unwire()
        logger.info("Dependency injection system shutdown")
    except Exception as e:
        logger.warning(f"Error during DI system shutdown: {e}")


def ensure_di_initialized() -> None:
    """Ensure DI system is initialized (called automatically on import)."""
    if not hasattr(ensure_di_initialized, '_initialized'):
        initialize_di_system()
        ensure_di_initialized._initialized = True


# Auto-initialize when module is imported
ensure_di_initialized()
