import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class RecordsManager(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.RECORDS_MANAGER, config=config)
        self.logger.debug("Initializing records manager")

    async def _initialize(self) -> None:
        """Initialize records manager-specific components."""
        self.logger.debug("Initializing records manager")
        # TODO: Implement records manager initialization

    async def _on_start(self) -> None:
        """Start the records manager."""
        self.logger.debug("Starting records manager")
        # TODO: Implement records manager start

    async def _on_stop(self) -> None:
        """Stop the records manager."""
        self.logger.debug("Stopping records manager")
        # TODO: Implement records manager stop

    async def _cleanup(self) -> None:
        """Clean up records manager-specific components."""
        self.logger.debug("Cleaning up records manager")
        # TODO: Implement records manager cleanup

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement records manager message processing


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())
