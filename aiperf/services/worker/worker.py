import asyncio
import sys
import uuid

import uvloop

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    ServiceType,
    Topic,
    ClientType,
)
from aiperf.common.models.credits import CreditReturn
from aiperf.common.models.messages import (
    ConversationData,
    CreditMessage,
    ResultData,
    ResultMessage,
)
from aiperf.common.models.push_pull import PushPullData
from aiperf.common.models.request_response import (
    RequestData,
    ResponseData,
    WorkerRequestPayload,
)
from aiperf.common.service.base import ServiceBase


class Worker(ServiceBase):
    """Worker responsible for sending requests to the server."""

    def __init__(self, service_config: ServiceConfig, service_id: str = None) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")
        await self.communication.create_clients(
            ClientType.CREDIT_RETURN_PUSH,
            ClientType.CREDIT_DROP_PULL,
            ClientType.CONVERSATION_DATA_REQ,
        )

    async def run(self) -> None:
        """Run the worker."""
        self.logger.debug("Running worker")

        await self._base_init()

        await self._initialize()
        await self._on_start()

        # Wait for the worker to finish
        # TODO: implement actual worker run logic
        await self.stop_event.wait()

        await self._on_stop()
        await self._cleanup()

    async def _on_start(self) -> None:
        """Start the worker."""
        self.logger.debug("Starting worker")
        # Subscribe to the credit drop topic
        await self.communication.pull(
            ClientType.CREDIT_DROP_PULL,
            Topic.CREDIT_DROP,
            self._process_credit_drop,
        )

    async def _on_stop(self) -> None:
        """Stop the worker."""
        self.logger.debug("Stopping worker")

    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        self.logger.debug("Cleaning up worker")

    async def _process_credit_drop(self, pull_data: PushPullData) -> None:
        """Process a credit drop message.

        Args:
            pull_data: The data received from the pull request
        """
        self.logger.debug(f"Processing credit drop: {pull_data}")

        await asyncio.sleep(1)  # Simulate some processing time
        
        # await self.communication.request(
        #     ClientType.CONVERSATION_DATA_REQ,
        #     target=ServiceType.DATASET_MANAGER,
        #     request_data=RequestData(
        #         request_id=f"req_{uuid.uuid4().hex[:8]}",
        #         client_id=self.service_id,
        #         target=ServiceType.DATASET_MANAGER,
        #         payload=WorkerRequestPayload(
        #             operation="get_conversation_data",
        #             parameters={},
        #         ),
        #     ),
        # )

        self.logger.debug("Returning credits")
        (
            await self.communication.push(
                ClientType.CREDIT_RETURN_PUSH,
                PushPullData(
                    topic=Topic.CREDIT_RETURN,
                    source=self.service_id,
                    data=CreditReturn(amount=1),
                ),
            ),
        )

    async def send_request(
        self, operation: str, parameters: dict = None, target: str = None
    ) -> ResponseData:
        """Send a structured request to the target service.

        Args:
            operation: The operation to perform
            parameters: Operation parameters
            target: Target service (defaults to system_controller)

        Returns:
            The response from the service
        """
        if not self.communication:
            self.logger.error("Communication not initialized")
            return ResponseData(
                request_id=f"error_{uuid.uuid4().hex[:8]}",
                client_id=self.service_id,
                status="error",
                message="Communication not initialized",
            )

        # Create the request payload
        request_payload = WorkerRequestPayload(
            operation=operation,
            parameters=parameters or {},
        )

        # Create the request data
        request_data = RequestData(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            client_id=self.service_id,
            target=target or "system_controller",
            payload=request_payload,
        )

        try:
            return await self.communication.request(request_data.target, request_data)
        except Exception as e:
            self.logger.error(f"Error sending request: {e}")
            return ResponseData(
                request_id=request_data.request_id,
                client_id=self.service_id,
                status="error",
                message=f"Error sending request: {e}",
            )

    async def process_credit(self, credit_message: CreditMessage) -> None:
        """Process a credit from the system controller.

        Args:
            credit_message: The credit message to process
        """
        credit_data = credit_message.credit
        self.logger.debug(
            f"Processing credit {credit_data.credit_id} for {credit_data.request_count} requests"
        )

        # TODO: Implement actual credit processing logic

    async def handle_conversation(self, conversation_data: ConversationData) -> None:
        """Handle a conversation with the system.

        Args:
            conversation_data: The conversation data to handle
        """
        self.logger.debug(
            f"Handling conversation {conversation_data.conversation_id} with {len(conversation_data.turns)} turns"
        )

        # TODO: Implement conversation handling logic

    async def publish_result(self, metrics: dict, tags: list = None) -> None:
        """Publish a structured result to the records manager.

        Args:
            metrics: Dictionary of performance metrics
            tags: Optional list of tags
        """
        if not self.communication:
            self.logger.error("Communication not initialized")
            return

        # Create a structured result
        result_data = ResultData(
            result_id=f"result_{uuid.uuid4().hex[:8]}",
            metrics=metrics,
            tags=tags or [],
        )

        # Create the result message
        result_message = ResultMessage(
            service_id=self.service_id,
            service_type=self.service_type.value,
            result=result_data,
        )

        await self._publish_message(
            ClientType.COMPONENT_PUB, Topic.DATA, result_message
        )


if __name__ == "__main__":
    uvloop.install()

    # Load the service configuration
    from aiperf.common.config.loader import load_worker_config

    cfg = load_worker_config()
    worker = Worker(cfg)
    sys.exit(uvloop.run(worker.run()))
