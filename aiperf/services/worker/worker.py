#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import asyncio
import os
import sys

from aiperf.backend.openai_client import OpenAIBackendClient, OpenAIBackendClientConfig
from aiperf.common.comms.client_enums import (
    ClientType,
    PullClientType,
    PushClientType,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_cleanup,
    on_init,
    on_run,
    on_start,
    on_stop,
)
from aiperf.common.enums import BackendClientType, ServiceType, Topic
from aiperf.common.models import BackendClientConfig, CreditReturnPayload
from aiperf.common.service.base_service import BaseService


class Worker(BaseService):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker")

        # OpenAI client will be initialized in _initialize
        self.openai_client = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return [
            *(super().required_clients or []),
            PullClientType.CREDIT_DROP,
            PushClientType.CREDIT_RETURN,
        ]

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")

        # Get API key from environment variable or use a default for testing
        api_key = os.environ.get("OPENAI_API_KEY", "dummy-key-for-testing")

        # Create OpenAI client configuration
        openai_client_config = BackendClientConfig(
            backend_client_type=BackendClientType.OPENAI,
            client_config=OpenAIBackendClientConfig(
                api_key=api_key,
                url="http://127.0.0.1:8000/v1",  # Default OpenAI API endpoint
                model="gpt-3.5-turbo",  # Default model
            ),
        )

        # Initialize the OpenAI client
        self.openai_client = OpenAIBackendClient(cfg=openai_client_config)
        self.logger.info("OpenAI backend client initialized")

    @on_run
    async def _run(self) -> None:
        """Automatically start the worker in the run method."""
        await self.start()

    @on_start
    async def _start(self) -> None:
        """Start the worker."""
        self.logger.debug("Starting worker")
        # Subscribe to the credit drop topic
        await self.comms.pull(
            topic=Topic.CREDIT_DROP,
            callback=self._process_credit_drop,
        )

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker."""
        self.logger.debug("Stopping worker")

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        self.logger.debug("Cleaning up worker")

    async def _process_credit_drop(self, message) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug(f"Processing credit drop: {message}")

        try:
            # Extract the credit drop message payload
            if hasattr(message, "payload") and hasattr(message.payload, "amount"):
                credit_amount = message.payload.amount
                self.logger.info(f"Received {credit_amount} credit(s)")

                # Make a call to OpenAI API for each credit
                for _ in range(credit_amount):
                    await self._call_openai_api()
                    await asyncio.sleep(0.1)  # Small delay between calls
            else:
                self.logger.warning(
                    f"Received credit drop message without amount: {message}"
                )

        except Exception as e:
            self.logger.error(f"Error processing credit drop: {e}")

        finally:
            # Always return the credits
            self.logger.debug("Returning credits")
            await self.comms.push(
                topic=Topic.CREDIT_RETURN,
                message=self.create_message(
                    payload=CreditReturnPayload(amount=1),
                ),
            )

    async def _call_openai_api(self) -> None:
        """Make a call to the OpenAI API."""
        try:
            self.logger.debug("Calling OpenAI API")

            if not self.openai_client:
                self.logger.warning("OpenAI client not initialized, skipping API call")
                return

            # Sample messages for the API call
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "Tell me about NVIDIA AI performance testing.",
                },
            ]

            try:
                # Format payload for the API request
                formatted_payload = await self.openai_client.format_payload(
                    endpoint="v1/chat/completions", payload={"messages": messages}
                )

                # Send the request to the API
                record = await self.openai_client.send_request(
                    endpoint="v1/chat/completions", payload=formatted_payload
                )

                if record.valid:
                    self.logger.debug("OpenAI API call successful")
                    self.logger.info(
                        f"Record: {record.time_to_first_response_ns / 1e6} milliseconds. {record.time_to_last_response_ns / 1e6} milliseconds."
                    )
                else:
                    self.logger.warning("OpenAI API call returned invalid response")

            except NotImplementedError:
                # Handle the case where methods are not fully implemented
                self.logger.warning(
                    "OpenAI client methods not fully implemented, using fallback"
                )
                self.logger.info("Simulated OpenAI API call (fallback)")

        except Exception as e:
            self.logger.error("Error calling OpenAI API: %s", str(e))


async def run_workers(service_config: ServiceConfig):
    """Create and run multiple worker instances.

    Args:
        service_config: The service configuration for the worker.
    """
    tasks = []
    # Create multiple worker instances
    # This is just an example, you can adjust the number of workers as needed
    for i in range(32):
        worker = Worker(service_config=service_config, service_id=f"worker_{i}")
        tasks.append(asyncio.create_task(worker.run_forever()))
    await asyncio.gather(*tasks)


def main() -> None:
    """Main entry point for the worker."""

    import uvloop

    from aiperf.common.config.loader import load_service_config

    # Load the service configuration
    cfg = load_service_config()

    # Create and run the worker
    # worker = Worker(cfg)
    uvloop.run(run_workers(cfg))


if __name__ == "__main__":
    sys.exit(main())
