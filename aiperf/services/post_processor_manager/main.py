import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class PostProcessorManager(ServiceBase):
    """Manager responsible for post-processing results data."""

    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.POST_PROCESSOR_MANAGER, config=config)
        self.logger.debug("Initializing post processor manager")

    async def _initialize(self) -> None:
        """Initialize post processor manager-specific components."""
        self.logger.debug("Initializing post processor manager")
        # TODO: Implement post processor manager initialization

    async def _on_start(self) -> None:
        """Start the post processor manager."""
        self.logger.debug("Starting post processor manager")
        # TODO: Implement post processor manager start

    async def _on_stop(self) -> None:
        """Stop the post processor manager."""
        self.logger.debug("Stopping post processor manager")
        # TODO: Implement post processor manager stop

    async def _cleanup(self) -> None:
        """Clean up post processor manager-specific components."""
        self.logger.debug("Cleaning up post processor manager")
        # TODO: Implement post processor manager cleanup

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement post processor manager message processing


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(PostProcessorManager)


if __name__ == "__main__":
    sys.exit(main())
