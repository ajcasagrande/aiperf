#!/usr/bin/env python3
"""
Component initialization for AIPerf.

This module ensures proper component registration and initialization.
"""

import asyncio
import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Type, Union

from .common.communication import Communication, MemoryCommunication
from .common.base_manager import BaseManager
from .config.config_models import AIPerfConfig, DatasetConfig, RecordsConfig
from .dataset.enhanced_dataset_manager import EnhancedDatasetManager
from .records.enhanced_records_manager import EnhancedRecordsManager
from .system.system_controller import SystemController
from .timing.timing_manager import TimingManager
from .workers.worker_manager import WorkerManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("aiperf.component_init")


async def initialize_communication(
    config: AIPerfConfig, client_id: Optional[str] = None
) -> Communication:
    """Initialize the communication system.

    Args:
        config: AIPerf configuration
        client_id: Optional client ID

    Returns:
        Initialized Communication object
    """
    logger.info("Initializing communication system")

    if config.communication_type == "memory":
        return MemoryCommunication(client_id=client_id)
    else:
        # Default to memory communication for now
        logger.warning(
            f"Unsupported communication type: {config.communication_type}, using memory communication"
        )
        return MemoryCommunication(client_id=client_id)


async def initialize_dataset_manager(
    config: AIPerfConfig, communication: Communication
) -> EnhancedDatasetManager:
    """Initialize the dataset manager.

    Args:
        config: AIPerf configuration
        communication: Communication system

    Returns:
        Initialized DatasetManager object
    """
    logger.info("Initializing dataset manager")

    # Get dataset config
    dataset_config = config.dataset

    # Create the dataset manager
    dataset_manager = EnhancedDatasetManager(
        config=dataset_config,
        communication=communication,
    )

    # Initialize the dataset manager
    success = await dataset_manager.initialize()
    if not success:
        logger.error("Failed to initialize dataset manager")
        raise RuntimeError("Failed to initialize dataset manager")

    return dataset_manager


async def initialize_records_manager(
    config: AIPerfConfig, communication: Communication
) -> EnhancedRecordsManager:
    """Initialize the records manager.

    Args:
        config: AIPerf configuration
        communication: Communication system

    Returns:
        Initialized RecordsManager object
    """
    logger.info("Initializing records manager")

    # Get records config
    records_config = config.records

    # Create the records manager
    records_manager = EnhancedRecordsManager(
        config=records_config,
        communication=communication,
    )

    # Initialize the records manager
    success = await records_manager.initialize()
    if not success:
        logger.error("Failed to initialize records manager")
        raise RuntimeError("Failed to initialize records manager")

    return records_manager


async def initialize_timing_manager(
    config: AIPerfConfig, communication: Communication
) -> TimingManager:
    """Initialize the timing manager.

    Args:
        config: AIPerf configuration
        communication: Communication system

    Returns:
        Initialized TimingManager object
    """
    logger.info("Initializing timing manager")

    # Get timing config
    timing_config = config.timing

    # Create the timing manager
    timing_manager = TimingManager(
        config=timing_config,
        communication=communication,
    )

    # Initialize the timing manager
    success = await timing_manager.initialize()
    if not success:
        logger.error("Failed to initialize timing manager")
        raise RuntimeError("Failed to initialize timing manager")

    return timing_manager


async def initialize_worker_manager(
    config: AIPerfConfig, communication: Communication
) -> WorkerManager:
    """Initialize the worker manager.

    Args:
        config: AIPerf configuration
        communication: Communication system

    Returns:
        Initialized WorkerManager object
    """
    logger.info("Initializing worker manager")

    # Get worker config
    worker_config = config.workers

    # Create the worker manager
    worker_manager = WorkerManager(
        config=worker_config,
        communication=communication,
    )

    # Initialize the worker manager
    success = await worker_manager.initialize()
    if not success:
        logger.error("Failed to initialize worker manager")
        raise RuntimeError("Failed to initialize worker manager")

    return worker_manager


async def initialize_system_controller(
    config: AIPerfConfig,
    communication: Communication,
    dataset_manager: Optional[EnhancedDatasetManager] = None,
    records_manager: Optional[EnhancedRecordsManager] = None,
    timing_manager: Optional[TimingManager] = None,
    worker_manager: Optional[WorkerManager] = None,
) -> SystemController:
    """Initialize the system controller.

    Args:
        config: AIPerf configuration
        communication: Communication system
        dataset_manager: Optional dataset manager
        records_manager: Optional records manager
        timing_manager: Optional timing manager
        worker_manager: Optional worker manager

    Returns:
        Initialized SystemController object
    """
    logger.info("Initializing system controller")

    # Create the system controller
    system_controller = SystemController(
        config=config,
        communication=communication,
    )

    # Register components if provided
    if dataset_manager:
        system_controller.register_component("dataset_manager", dataset_manager)
    if records_manager:
        system_controller.register_component("records_manager", records_manager)
    if timing_manager:
        system_controller.register_component("timing_manager", timing_manager)
    if worker_manager:
        system_controller.register_component("worker_manager", worker_manager)

    # Initialize the system controller
    success = await system_controller.initialize()
    if not success:
        logger.error("Failed to initialize system controller")
        raise RuntimeError("Failed to initialize system controller")

    return system_controller


async def initialize_all_components(config: AIPerfConfig) -> Dict[str, Any]:
    """Initialize all AIPerf components.

    Args:
        config: AIPerf configuration

    Returns:
        Dictionary with initialized components
    """
    logger.info("Initializing all AIPerf components")

    try:
        # Initialize communication
        communication = await initialize_communication(
            config, client_id="system_initialization"
        )

        # Initialize component managers
        dataset_manager = await initialize_dataset_manager(config, communication)
        records_manager = await initialize_records_manager(config, communication)
        timing_manager = await initialize_timing_manager(config, communication)
        worker_manager = await initialize_worker_manager(config, communication)

        # Initialize system controller
        system_controller = await initialize_system_controller(
            config,
            communication,
            dataset_manager,
            records_manager,
            timing_manager,
            worker_manager,
        )

        return {
            "communication": communication,
            "dataset_manager": dataset_manager,
            "records_manager": records_manager,
            "timing_manager": timing_manager,
            "worker_manager": worker_manager,
            "system_controller": system_controller,
        }
    except Exception as e:
        logger.error(f"Error initializing AIPerf components: {e}")
        traceback.print_exc()
        raise


async def start_all_components(components: Dict[str, Any]) -> bool:
    """Start all AIPerf components.

    Args:
        components: Dictionary with components

    Returns:
        True if all components started successfully, False otherwise
    """
    logger.info("Starting all AIPerf components")

    try:
        # Get system controller
        system_controller = components.get("system_controller")
        if not system_controller:
            logger.error("System controller not found")
            return False

        # Start all components through the system controller
        success = await system_controller.start_profile()
        if not success:
            logger.error("Failed to start all components")
            return False

        logger.info("All AIPerf components started successfully")
        return True
    except Exception as e:
        logger.error(f"Error starting AIPerf components: {e}")
        traceback.print_exc()
        return False


async def stop_all_components(components: Dict[str, Any]) -> bool:
    """Stop all AIPerf components.

    Args:
        components: Dictionary with components

    Returns:
        True if all components stopped successfully, False otherwise
    """
    logger.info("Stopping all AIPerf components")

    try:
        # Get system controller
        system_controller = components.get("system_controller")
        if not system_controller:
            logger.error("System controller not found")
            return False

        # Stop all components through the system controller
        success = await system_controller.stop_profile()
        if not success:
            logger.error("Failed to stop all components")
            return False

        logger.info("All AIPerf components stopped successfully")
        return True
    except Exception as e:
        logger.error(f"Error stopping AIPerf components: {e}")
        traceback.print_exc()
        return False


async def shutdown_all_components(components: Dict[str, Any]) -> bool:
    """Shutdown all AIPerf components.

    Args:
        components: Dictionary with components

    Returns:
        True if all components shut down successfully, False otherwise
    """
    logger.info("Shutting down all AIPerf components")

    try:
        # First stop if running
        await stop_all_components(components)

        # Get system controller
        system_controller = components.get("system_controller")
        if system_controller:
            await system_controller.shutdown()

        # Shutdown individual components just in case
        for name, component in components.items():
            if name != "communication" and hasattr(component, "shutdown"):
                try:
                    await component.shutdown()
                except Exception as e:
                    logger.warning(f"Error shutting down {name}: {e}")

        # Shutdown communication last
        communication = components.get("communication")
        if communication:
            try:
                await communication.close()
            except Exception as e:
                logger.warning(f"Error closing communication: {e}")

        logger.info("All AIPerf components shut down successfully")
        return True
    except Exception as e:
        logger.error(f"Error shutting down AIPerf components: {e}")
        traceback.print_exc()
        return False
