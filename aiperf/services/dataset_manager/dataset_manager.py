import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.models.base_models import BasePayload
from aiperf.common.service.component import ComponentServiceBase


class DatasetManager(ComponentServiceBase):
    def __init__(self, service_config: ServiceConfig, service_id: str = None) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing dataset manager")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.DATASET_MANAGER

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

    async def _configure(self, payload: BasePayload) -> None:
        """Configure the dataset manager."""
        self.logger.debug(f"Configuring dataset manager with payload: {payload}")
        # TODO: Implement dataset manager configuration


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManager)


if __name__ == "__main__":
    sys.exit(main())
