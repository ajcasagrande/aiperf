#!/usr/bin/env python3
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
logger = logging.getLogger("worker_test")

# Add parent directory to path for imports
sys.path.append(os.path.abspath("."))

from aiperf.config.config_models import EndpointConfig, AuthConfig
from aiperf.workers.concrete_worker import ConcreteWorker
from aiperf.api.openai_client import OpenAIClient


async def test_worker_initialization():
    logging.info("Testing worker initialization...")
    client = None
    worker = None

    try:
        # Create endpoint config with debug mode
        endpoint_config = EndpointConfig(
            name="test_endpoint",
            url="https://api.openai.com/v1",
            api_type="openai",
            headers={"Content-Type": "application/json"},
            auth=AuthConfig(api_key="YOUR_API_KEY"),
            timeout=30.0,
            metadata={"debug_mode": True, "description": "Test endpoint"},
        )

        # Debug: Print endpoint config
        logging.debug(f"Endpoint config: {endpoint_config}")
        logging.debug(
            f"Metadata debug_mode: {endpoint_config.metadata.get('debug_mode')}"
        )

        # First test the OpenAI client directly
        logging.info("Testing OpenAI client directly...")
        client = OpenAIClient(endpoint_config)
        logging.debug(
            f"Created client with debug mode: {endpoint_config.metadata.get('debug_mode')}"
        )
        try:
            client_init = await client.initialize()
            logging.info(
                f"OpenAI client initialization: {'SUCCESS' if client_init else 'FAILED'}"
            )

            # Test a request with the client
            if client_init:
                logging.info("Testing client send_request...")
                request_data = {
                    "messages": [{"role": "user", "content": "Hello, how are you?"}],
                    "model": "gpt-3.5-turbo",
                }
                response = await client.send_request(request_data)
                logging.info(
                    f"Client request success: {response.get('success', False)}, is_mock: {response.get('is_mock', False)}"
                )
        except Exception as e:
            logging.error(f"Error in OpenAI client test: {e}", exc_info=True)

        # Create worker instance
        try:
            worker = ConcreteWorker(endpoint_config)
            logging.info("Initializing worker...")
            worker_init = await worker.initialize()
            logging.info(
                f"Worker initialization: {'SUCCESS' if worker_init else 'FAILED'}"
            )

            # Test a request with the worker
            if worker_init:
                logging.info("Testing worker send_request...")
                request_data = {
                    "messages": [{"role": "user", "content": "Tell me a joke."}],
                    "model": "gpt-3.5-turbo",
                }
                response = await worker.send_request(request_data)
                if response:
                    logging.info(
                        f"Worker request success: {response.get('success', False)}, is_mock: {response.get('is_mock', False)}"
                    )
                else:
                    logging.error("Worker request failed with None response")

        except Exception as e:
            logging.error(f"Error in worker test: {e}", exc_info=True)

        logging.info("Worker initialization tests complete")

    finally:
        # Clean up resources
        logging.info("Cleaning up resources...")
        if worker:
            await worker.shutdown()
            logging.info("Worker shut down successfully")
        if client:
            await client.shutdown()
            logging.info("Client shut down successfully")


async def test_mock_server_fallback():
    """Test the fallback to mock responses when a mock server returns 404."""
    logging.info("Testing mock server 404 fallback...")
    client = None

    try:
        # Create endpoint config with debug mode but pointing to a mock server
        # that will likely return 404 for OpenAI endpoints
        endpoint_config = EndpointConfig(
            name="mock_server_test",
            url="http://localhost:8000",  # Mock server address
            api_type="openai",
            headers={"Content-Type": "application/json"},
            auth=AuthConfig(api_key="YOUR_API_KEY"),
            timeout=5.0,  # Shorter timeout for tests
            metadata={"debug_mode": True, "description": "Mock server test"},
        )

        # Create and initialize the client
        client = OpenAIClient(endpoint_config)
        init_success = await client.initialize()
        logging.info(
            f"Client initialization: {'SUCCESS' if init_success else 'FAILED'}"
        )

        if init_success:
            # Test sending a request that should receive a 404 from the mock server
            # but then fall back to the mock response
            request_data = {
                "messages": [
                    {
                        "role": "user",
                        "content": "This should go to a non-existent endpoint",
                    }
                ],
                "model": "gpt-3.5-turbo",
            }

            logging.info("Sending request to mock server (expecting 404 fallback)...")
            response = await client.send_request(request_data)

            # Check if we received a mock response despite the 404
            is_mock = response.get("is_mock", False)
            success = response.get("success", False)

            logging.info(
                f"Request to mock server - success: {success}, is_mock: {is_mock}"
            )

            if is_mock and success:
                logging.info("PASS: Successfully fell back to mock response on 404")
            else:
                logging.error("FAIL: Did not fall back to mock response properly")
                logging.debug(f"Response details: {response}")

    except Exception as e:
        logging.error(f"Error in mock server test: {e}", exc_info=True)
    finally:
        if client:
            await client.shutdown()
            logging.info("Client shut down")

    logging.info("Mock server fallback test complete")


async def main():
    try:
        await test_worker_initialization()

        await test_mock_server_fallback()
    except Exception as e:
        logging.error(f"Error in test: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Test interrupted by user")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}")
        traceback.print_exc()
