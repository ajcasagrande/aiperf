import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.models.base_models import BasePayload
from aiperf.common.service.component import ComponentServiceBase


class PostProcessorManager(ComponentServiceBase):
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

    async def _configure(self, payload: BasePayload) -> None:
        """Configure the post processor manager."""
        self.logger.debug(f"Configuring post processor manager with payload: {payload}")
        # TODO: Implement post processor manager configuration


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(PostProcessorManager)


if __name__ == "__main__":
    sys.exit(main())
