#!/usr/bin/env python3
"""
Test script to verify that our OpenAIClient correctly handles 404 errors from the mock server.
Run the mock_server.py script first, then run this script.
"""

import asyncio
import logging
import os
import sys
import traceback
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mock_server_test")

# Add parent directory to path for imports
sys.path.append(os.path.abspath("."))

from aiperf.config.config_models import EndpointConfig, AuthConfig
from aiperf.workers.concrete_worker import ConcreteWorker
from aiperf.api.openai_client import OpenAIClient


async def test_mock_server_client():
    """Test the OpenAIClient against a mock server that returns 404 errors."""
    logger.info("Testing OpenAIClient against mock server...")
    client = None

    try:
        # Create endpoint config pointing to the mock server
        endpoint_config = EndpointConfig(
            name="mock_server_test",
            url="http://localhost:8000",  # Mock server address
            api_type="openai",
            headers={"Content-Type": "application/json"},
            auth=AuthConfig(
                api_key="VALID_TEST_KEY"
            ),  # Use a non-placeholder key to force HTTP requests
            timeout=5.0,  # Shorter timeout for tests
            metadata={"debug_mode": True, "description": "Mock server test"},
        )

        logger.info(f"Connecting to mock server at {endpoint_config.url}")

        # Create and initialize the client
        client = OpenAIClient(endpoint_config)
        init_success = await client.initialize()
        logger.info(f"Client initialization: {'SUCCESS' if init_success else 'FAILED'}")

        if init_success:
            # Test standard request (should get 404 and fall back to mock)
            standard_request = {
                "messages": [
                    {"role": "user", "content": "This is a standard request test."}
                ],
                "model": "gpt-3.5-turbo",
            }

            logger.info(
                "Sending standard request to mock server (should receive 404)..."
            )
            standard_response = await client.send_request(standard_request)
            logger.info(
                f"Standard request - Success: {standard_response.get('success', False)}, "
                f"Is Mock: {standard_response.get('is_mock', False)}"
            )

            # Test streaming request (should get 404 and fall back to mock)
            streaming_request = {
                "messages": [
                    {"role": "user", "content": "This is a streaming request test."}
                ],
                "model": "gpt-3.5-turbo",
                "stream": True,
            }

            logger.info(
                "Sending streaming request to mock server (should receive 404)..."
            )
            streaming_response = await client.send_request(streaming_request)
            logger.info(
                f"Streaming request - Success: {streaming_response.get('success', False)}, "
                f"Is Mock: {streaming_response.get('is_mock', False)}"
            )

            # Verify that both requests were successful despite the 404s
            if (
                standard_response.get("success", False)
                and standard_response.get("is_mock", False)
                and streaming_response.get("success", False)
                and streaming_response.get("is_mock", False)
            ):
                logger.info(
                    "✅ SUCCESS: Both requests successfully fell back to mock responses after 404"
                )
            else:
                logger.error(
                    "❌ FAIL: One or more requests did not fall back to mock responses"
                )

    except Exception as e:
        logger.error(f"Error during mock server test: {e}", exc_info=True)
    finally:
        if client:
            await client.shutdown()
            logger.info("Client resources cleaned up")

    logger.info("Mock server test completed")


async def test_worker_with_mock_server():
    """Test a ConcreteWorker against a mock server that returns 404 errors."""
    logger.info("Testing ConcreteWorker against mock server...")
    worker = None

    try:
        # Create endpoint config pointing to the mock server
        endpoint_config = EndpointConfig(
            name="mock_server_test",
            url="http://localhost:8000",  # Mock server address
            api_type="openai",
            headers={"Content-Type": "application/json"},
            auth=AuthConfig(
                api_key="VALID_TEST_KEY"
            ),  # Use a non-placeholder key to force HTTP requests
            timeout=5.0,  # Shorter timeout for tests
            metadata={"debug_mode": True, "description": "Mock server test"},
        )

        # Create and initialize the worker
        worker = ConcreteWorker(endpoint_config)
        init_success = await worker.initialize()
        logger.info(f"Worker initialization: {'SUCCESS' if init_success else 'FAILED'}")

        if init_success:
            # Test sending a request through the worker
            request_data = {
                "messages": [
                    {"role": "user", "content": "Test message through worker"}
                ],
                "model": "gpt-3.5-turbo",
            }

            logger.info(
                "Sending request through worker to mock server (should receive 404)..."
            )
            response = await worker.send_request(request_data)

            if (
                response
                and response.get("success", False)
                and response.get("is_mock", False)
            ):
                logger.info(
                    "✅ SUCCESS: Worker request successfully fell back to mock response after 404"
                )
            else:
                logger.error(
                    "❌ FAIL: Worker request did not fall back to mock response"
                )
                logger.debug(f"Response details: {response}")

    except Exception as e:
        logger.error(f"Error during worker test: {e}", exc_info=True)
    finally:
        if worker:
            await worker.shutdown()
            logger.info("Worker resources cleaned up")

    logger.info("Worker with mock server test completed")


async def main():
    """Run all tests against the mock server."""
    try:
        # Run the OpenAIClient test
        await test_mock_server_client()

        # Run the ConcreteWorker test
        await test_worker_with_mock_server()

    except Exception as e:
        logger.error(f"Error in main test function: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        traceback.print_exc()
