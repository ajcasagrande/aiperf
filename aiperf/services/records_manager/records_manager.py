import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.models.base_models import BasePayload
from aiperf.common.service.component import ComponentServiceBase


class RecordsManager(ComponentServiceBase):
    def __init__(self, service_config: ServiceConfig, service_id: str = None) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing records manager")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.RECORDS_MANAGER

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

    async def _configure(self, payload: BasePayload) -> None:
        """Configure the records manager."""
        self.logger.debug(f"Configuring records manager with payload: {payload}")
        # TODO: Implement records manager configuration


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())
