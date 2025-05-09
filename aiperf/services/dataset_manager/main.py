import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class DatasetManager(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.DATASET_MANAGER, config=config)
        self.logger.debug("Initializing dataset manager")

    async def _initialize(self) -> None:
        """Initialize dataset manager-specific components."""
        self.logger.debug("Initializing dataset manager")
        # TODO: Implement dataset manager initialization

    async def _on_start(self) -> None:
        """Start the dataset manager."""
        self.logger.debug("Starting dataset manager")
        # TODO: Implement dataset manager start

    async def _on_stop(self) -> None:
        """Stop the dataset manager."""
        self.logger.debug("Stopping dataset manager")
        # TODO: Implement dataset manager stop

    async def _cleanup(self) -> None:
        """Clean up dataset manager-specific components."""
        self.logger.debug("Cleaning up dataset manager")
        # TODO: Implement dataset manager cleanup

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement dataset manager message processing


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManager)


if __name__ == "__main__":
    sys.exit(main())
