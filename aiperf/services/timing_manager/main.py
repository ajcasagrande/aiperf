import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase


class TimingManager(ServiceBase):
    def __init__(self, config: ServiceConfig):
        super().__init__(service_type="timing_manager", config=config)

    async def _initialize(self) -> None:
        self.logger.debug("Initializing timing manager")

    async def _run(self) -> None:
        self.logger.debug("Starting timing manager")

    async def _stop(self) -> None:
        self.logger.debug("Stopping timing manager")

    async def _cleanup(self) -> None:
        self.logger.debug("Cleaning up timing manager")

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        self.logger.debug(f"Processing message in timing manager: {topic}, {message}")


def main() -> None:
    from aiperf.common.service import bootstrap_and_run_service

    bootstrap_and_run_service(TimingManager)


if __name__ == "__main__":
    sys.exit(main())
