import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class TimingManager(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.TIMING_MANAGER, config=config)
        self.logger.debug("Initializing timing manager")

    async def _initialize(self) -> None:
        """Initialize timing manager-specific components."""
        self.logger.debug("Initializing timing manager")
        # TODO: Implement timing manager initialization

    async def _on_start(self) -> None:
        """Start the timing manager."""
        self.logger.debug("Starting timing manager")
        # TODO: Implement timing manager start

    async def _on_stop(self) -> None:
        """Stop the timing manager."""
        self.logger.debug("Stopping timing manager")
        # TODO: Implement timing manager stop

    async def _cleanup(self) -> None:
        """Clean up timing manager-specific components."""
        self.logger.debug("Cleaning up timing manager")
        # TODO: Implement timing manager cleanup

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement timing manager message processing


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(TimingManager)


if __name__ == "__main__":
    sys.exit(main())
