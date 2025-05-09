import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class Worker(ServiceBase):
    """Worker responsible for sending requests to the server."""

    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.WORKER, config=config)
        self.logger.debug("Initializing worker")

    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")

    async def _on_start(self) -> None:
        """Start the worker."""
        self.logger.debug("Starting worker")

    async def _on_stop(self) -> None:
        """Stop the worker."""
        self.logger.debug("Stopping worker")

    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        self.logger.debug("Cleaning up worker")

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement message processing

    async def send_request(self, request: dict) -> dict:
        """Send a request to the target service.

        Args:
            request: The request to send

        Returns:
            The response from the service
        """
        # TODO: Implement sending requests
        return {"status": "ok"}

    async def process_credit(self, credit: dict) -> None:
        """Process a credit from the system controller.

        Args:
            credit: The credit to process
        """
        # TODO: Implement processing credits

    async def handle_conversation(self, conversation: dict) -> None:
        """Handle a conversation with the system.

        Args:
            conversation: The conversation to handle
        """
        # TODO: Implement conversation handling

    async def publish_result(self, result: dict) -> None:
        """Publish a result to the records manager.

        Args:
            result: The result to publish
        """
        # TODO: Implement publishing results


if __name__ == "__main__":
    import uvloop

    uvloop.install()

    # Load the service configuration
    from aiperf.common.config.loader import load_worker_config

    cfg = load_worker_config()
    worker = Worker(cfg)
    sys.exit(uvloop.run(worker.run()))
