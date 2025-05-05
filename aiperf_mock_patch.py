#!/usr/bin/env python3
"""
AIPerf Mock Patch

This script provides monkey patching for AIPerf to make it work with our mock OpenAI server.
It patches the memory communication module to provide mock responses for missing components.

Usage:
    python -m aiperf_mock_patch

This will apply the patches and then execute AIPerf with whatever arguments you passed.
"""

import sys
import importlib
import asyncio
import types
import logging
import json
from typing import Dict, Any, Callable, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("aiperf_mock_patch")


def apply_patches():
    """Apply all patches to AIPerf for mock server usage."""
    logger.info("Applying AIPerf mock patches...")

    # Patch the MemoryCommunication module
    patch_memory_communication()

    # Patch the WorkerManager module
    patch_worker_manager()

    logger.info("Patches applied successfully!")


def patch_memory_communication():
    """Patch the MemoryCommunication module to provide mock responses."""
    try:
        # Import the module
        from aiperf.common import memory_communication

        MemoryCommunication = memory_communication.MemoryCommunication
        logger.info("Patching MemoryCommunication...")

        # Store original methods
        original_request = MemoryCommunication.request

        # Define new request method
        async def patched_request(
            self, target: str, request: Dict[str, Any], timeout: float = 5.0
        ) -> Dict[str, Any]:
            """Patched request method that provides mock responses for missing components."""
            # Special handling for dataset_manager and records_manager
            if target in ["dataset_manager", "records_manager"]:
                # Try to find the actual component ID
                actual_target = None
                for client_id in MemoryCommunication._requests.keys():
                    if target == "dataset_manager" and client_id.startswith(
                        "dataset_manager_"
                    ):
                        actual_target = client_id
                        logger.info(
                            f"[PATCH] Resolved dataset_manager to {actual_target}"
                        )
                        break
                    elif target == "records_manager" and client_id.startswith(
                        "records_manager_"
                    ):
                        actual_target = client_id
                        logger.info(
                            f"[PATCH] Resolved records_manager to {actual_target}"
                        )
                        break

                if actual_target:
                    target = actual_target

            # Check if target exists before calling original method
            if target not in MemoryCommunication._requests:
                logger.warning(
                    f"[PATCH] Target component not found: {target}, providing mock response"
                )

                # Create mock responses based on the request
                command = request.get("command", "")

                if target == "dataset_manager":
                    if command == "get_synthetic_prompt":
                        return {
                            "status": "success",
                            "prompt": {
                                "content": "This is a mock synthetic prompt for testing",
                                "modality": "text",
                                "metadata": {"synthetic": True},
                            },
                        }
                    elif command == "get_conversation":
                        return {
                            "status": "success",
                            "conversation": {
                                "conversation_id": "mock_conversation_id",
                                "turns": [
                                    {
                                        "request": "What is AI?",
                                        "response": "AI is artificial intelligence",
                                        "success": True,
                                    }
                                ],
                                "metadata": {"synthetic": True},
                            },
                        }
                    elif command == "get_next_turn":
                        return {
                            "status": "success",
                            "turn": {
                                "request": "What is AI?",
                                "response": None,
                                "metadata": {"synthetic": True},
                            },
                        }
                    else:
                        return {
                            "status": "success",
                            "message": f"Mock dataset_manager response for command: {command}",
                        }

                elif target == "records_manager":
                    if command == "store_record":
                        return {"status": "success", "message": "Record stored (mock)"}
                    elif command == "get_records":
                        return {"status": "success", "records": []}
                    else:
                        return {
                            "status": "success",
                            "message": f"Mock records_manager response for command: {command}",
                        }

                return {
                    "status": "success",
                    "message": f"Mock response for {target}:{command}",
                }

            # Call original method for existing targets
            return await original_request(self, target, request, timeout)

        # Apply patch
        MemoryCommunication.request = patched_request
        logger.info("MemoryCommunication.request patched successfully")

        # Store original publish method
        original_publish = MemoryCommunication.publish

        # Define new publish method
        async def patched_publish(self, topic: str, message: Dict[str, Any]) -> bool:
            """Patched publish method with enhanced logging and special handling for important topics."""
            # Debug logging for important topics
            if topic in [
                "timing.credit.issued",
                "system.identity",
                "dataset.request",
                "records.request",
            ]:
                logger.info(
                    f"[PATCH] Publishing to topic {topic} from {self.client_id}"
                )

            # Handle topic creation if needed
            if topic not in MemoryCommunication._topics:
                MemoryCommunication._topics[topic] = set()
                logger.info(f"[PATCH] Created new topic during publish: {topic}")

            # Special handling for system.identity messages
            if (
                topic == "system.identity"
                and isinstance(message, dict)
                and "component_type" in message
            ):
                component_type = message.get("component_type")
                component_id = message.get("component_id")
                logger.info(
                    f"[PATCH] Registering component: {component_id} of type {component_type}"
                )

                # Create component-specific topics if needed
                if component_type == "dataset_manager":
                    if "dataset.request" not in MemoryCommunication._topics:
                        MemoryCommunication._topics["dataset.request"] = set()
                    MemoryCommunication._topics["dataset.request"].add(self.client_id)
                    logger.info(
                        f"[PATCH] Registered {component_id} for dataset.request"
                    )

                elif component_type == "records_manager":
                    if "records.request" not in MemoryCommunication._topics:
                        MemoryCommunication._topics["records.request"] = set()
                    MemoryCommunication._topics["records.request"].add(self.client_id)
                    logger.info(
                        f"[PATCH] Registered {component_id} for records.request"
                    )

            # Call original method
            result = await original_publish(self, topic, message)

            # Make sure our timings are properly distributed
            if topic == "timing.credit.issued" and result:
                # Ensure all subscribers receive the message
                if len(MemoryCommunication._topics.get(topic, set())) == 0:
                    logger.warning(
                        f"[PATCH] No subscribers for {topic}, message might be lost"
                    )

            return result

        # Apply patch
        MemoryCommunication.publish = patched_publish
        logger.info("MemoryCommunication.publish patched successfully")

    except ImportError:
        logger.error("Could not import aiperf.common.memory_communication")
        return False

    return True


def patch_worker_manager():
    """Patch the WorkerManager to handle missing component issues."""
    try:
        # Import the module
        from aiperf.workers import worker_manager

        WorkerManager = worker_manager.WorkerManager
        logger.info("Patching WorkerManager...")

        # Store original method
        original_process_credit = WorkerManager.process_credit

        # Define new process_credit method
        async def patched_process_credit(self, credit):
            """Patched process_credit method that handles missing components gracefully."""
            logger.info(f"[PATCH] Processing credit: {credit.credit_id}")

            try:
                # Call original method
                result = await original_process_credit(self, credit)
                return result
            except Exception as e:
                logger.warning(f"[PATCH] Error in process_credit: {e}")
                # Handle the error gracefully and continue
                return True

        # Apply patch
        WorkerManager.process_credit = patched_process_credit
        logger.info("WorkerManager.process_credit patched successfully")

    except ImportError:
        logger.error("Could not import aiperf.workers.worker_manager")
        return False

    return True


def main():
    """Main entry point for the patch script."""
    # Apply patches
    apply_patches()

    # Now run the original AIPerf CLI
    try:
        from aiperf.cli import aiperf_cli

        # Keep the original sys.argv
        aiperf_cli.main()
    except ImportError:
        logger.error("Could not import aiperf.cli.aiperf_cli")
        sys.exit(1)


if __name__ == "__main__":
    main()
