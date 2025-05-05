import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class RecordsManager(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type="records_manager", config=config)

    async def _initialize(self) -> None:
        self.logger.debug("Initializing records manager")

    async def _run(self) -> None:
        self.logger.debug("Starting records manager")

    async def _stop(self) -> None:
        self.logger.debug("Stopping records manager")

    async def _cleanup(self) -> None:
        self.logger.debug("Cleaning up records manager")

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        self.logger.debug(f"Processing message in records manager: {topic}, {message}")


def main() -> None:
    from aiperf.common.service import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())
