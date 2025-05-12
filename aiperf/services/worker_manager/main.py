import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class WorkerManager(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.WORKER_MANAGER, config=config)
        self.logger.debug("Initializing worker manager")

    async def _initialize(self) -> None:
        """Initialize worker manager-specific components."""
        self.logger.debug("Initializing worker manager")
        # TODO: Implement worker manager initialization

    async def _on_start(self) -> None:
        """Start the worker manager."""
        self.logger.debug("Starting worker manager")
        # TODO: Implement worker manager start
        # TODO: Spawn worker processes

    async def _on_stop(self) -> None:
        """Stop the worker manager."""
        self.logger.debug("Stopping worker manager")
        # TODO: Implement worker manager stop

    async def _cleanup(self) -> None:
        """Clean up worker manager-specific components."""
        self.logger.debug("Cleaning up worker manager")
        # TODO: Implement worker manager cleanup

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement worker manager message processing


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(WorkerManager)


if __name__ == "__main__":
    sys.exit(main())
