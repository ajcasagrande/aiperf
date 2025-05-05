#!/usr/bin/env python3
"""
Comprehensive test for AIPerf with full component implementations.

This test creates a complete AIPerf system with real components instead
of mocks, and verifies that everything works end-to-end.
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from typing import Dict, Any, List, Tuple

from aiperf.component_init import (
    initialize_all_components,
    start_all_components,
    stop_all_components,
    shutdown_all_components,
)
from aiperf.config.config_models import (
    AIPerfConfig,
    DatasetConfig,
    RecordsConfig,
    TimingConfig,
    WorkerConfig,
    ClientConfig,
    AuthConfig,
)
from aiperf.dataset.enhanced_dataset_manager import EnhancedDatasetManager
from aiperf.records.enhanced_records_manager import EnhancedRecordsManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_full_components")


def create_test_config() -> AIPerfConfig:
    """Create a test configuration for AIPerf.

    Returns:
        Test configuration
    """
    # Create temporary directories for storage
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="aiperf_test_")
    dataset_cache_dir = os.path.join(temp_dir, "dataset_cache")
    records_storage_dir = os.path.join(temp_dir, "records")
    os.makedirs(dataset_cache_dir, exist_ok=True)
    os.makedirs(records_storage_dir, exist_ok=True)

    # Create dataset config
    dataset_config = DatasetConfig(
        name="test_dataset",
        source_type="synthetic",
        modality="text",
        cache_dir=dataset_cache_dir,
        synthetic_params={
            "seed": 42,
            "pre_generate": 5,
        },
    )

    # Create records config
    records_config = RecordsConfig(
        storage_path=records_storage_dir,
        auto_save=True,
        save_interval=5,
        publish_events=True,
    )

    # Create timing config
    timing_config = TimingConfig(
        distribution="uniform",
        params={
            "min_interval": 0.5,
            "max_interval": 2.0,
        },
        credit_ttl=10.0,
    )

    # Create client config
    openai_config = ClientConfig(
        client_type="openai",
        api_key="dummy_key_for_testing",
        auth=AuthConfig(
            api_key="dummy_key_for_testing",
        ),
        parameters={
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 100,
        },
        base_url="http://localhost:8000/v1",  # Point to our mock server
    )

    # Create worker config
    worker_config = WorkerConfig(
        worker_count=2,
        clients=[openai_config],
    )

    # Create main config
    config = AIPerfConfig(
        profile_name="test_profile",
        communication_type="memory",
        dataset=dataset_config,
        records=records_config,
        timing=timing_config,
        workers=worker_config,
    )

    return config


async def run_test_with_wait(
    components: Dict[str, Any],
    duration: float = 10.0,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Run the test by starting all components and waiting for completion.

    Args:
        components: Dictionary with components
        duration: Duration to run the test in seconds

    Returns:
        Tuple of (success boolean, list of records)
    """
    # Start all components
    success = await start_all_components(components)
    if not success:
        logger.error("Failed to start components")
        return False, []

    # Get the records manager for checking results
    records_manager = components.get("records_manager")
    if not records_manager:
        logger.error("Records manager not found")
        return False, []

    # Wait for the specified duration
    logger.info(f"Test running for {duration} seconds...")
    await asyncio.sleep(duration)

    # Stop all components
    success = await stop_all_components(components)
    if not success:
        logger.error("Failed to stop components")
        # Continue anyway to check results

    # Get all records
    records = await records_manager.query_records({}, limit=1000)
    logger.info(f"Found {len(records)} records after test")

    return True, records


async def verify_test_results(records: List[Dict[str, Any]]) -> bool:
    """Verify the test results.

    Args:
        records: List of records from the test

    Returns:
        True if verification passed, False otherwise
    """
    # Check if we have any records
    if not records:
        logger.error("No records found")
        return False

    # Check record structure
    for i, record in enumerate(records):
        # Check basic fields
        if "record_id" not in record:
            logger.error(f"Record {i} missing record_id")
            return False

        # Check conversation data
        if "conversation" not in record:
            logger.error(f"Record {record['record_id']} missing conversation")
            return False

        conversation = record["conversation"]
        if "turns" not in conversation:
            logger.error(
                f"Conversation {conversation.get('conversation_id', 'unknown')} missing turns"
            )
            return False

        # Check metrics
        if "metrics" not in record:
            logger.error(f"Record {record['record_id']} missing metrics")
            return False

        metrics = record["metrics"]
        if not isinstance(metrics, list) or not metrics:
            logger.error(f"Record {record['record_id']} has invalid metrics format")
            return False

    logger.info("All records validated successfully")
    return True


async def run_full_system_test():
    """Run a comprehensive test of the full AIPerf system."""
    start_time = time.time()
    logger.info("Starting full system test with real components")

    # Create the configuration
    config = create_test_config()
    logger.info(f"Created test configuration with profile: {config.profile_name}")

    # Initialize components
    components = None
    try:
        components = await initialize_all_components(config)
        logger.info("Successfully initialized all components")

        # Verify dataset manager
        dataset_manager = components.get("dataset_manager")
        if not dataset_manager:
            logger.error("Dataset manager not initialized")
            return False

        # Verify initial dataset
        conversation = await dataset_manager.get_conversation()
        if not conversation:
            logger.error("Failed to get a conversation from dataset")
            return False

        logger.info(
            f"Dataset initialized with conversation ID: {conversation.conversation_id}"
        )

        # Run the test
        success, records = await run_test_with_wait(components, duration=15.0)
        if not success:
            logger.error("Test execution failed")
            return False

        # Verify the test results
        result = await verify_test_results(records)

        if result:
            logger.info("Full system test PASSED")
        else:
            logger.error("Full system test FAILED")

        return result

    except Exception as e:
        logger.error(f"Error in full system test: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up
        if components:
            await shutdown_all_components(components)
            logger.info("All components shut down")

        elapsed = time.time() - start_time
        logger.info(f"Full system test completed in {elapsed:.2f} seconds")


if __name__ == "__main__":
    # Run the full system test
    result = asyncio.run(run_full_system_test())

    # Set exit code based on result
    sys.exit(0 if result else 1)
