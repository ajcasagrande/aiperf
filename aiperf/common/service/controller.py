from abc import ABC

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ClientType, ServiceType, ServiceState
from aiperf.common.service.base import ServiceBase


class ControllerServiceBase(ServiceBase, ABC):
    """Base class for all controller services.

    This class provides a common interface for all controller services in the AIPerf framework.
    It inherits from the ServiceBase class and implements the required methods for controller
    services.
    """

    def __init__(self, service_type: ServiceType, config: ServiceConfig) -> None:
        super().__init__(service_type=service_type, config=config)

    # TODO: Complete the implementation of the controller service methods
    async def run(self) -> None:
        """Start the service and initialize its components."""
        await self._base_init()

        await self.communication.create_clients(
            ClientType.CONTROLLER_SUB,
            ClientType.COMPONENT_PUB,
        )

        await self._initialize()

        await self._set_service_status(ServiceState.READY)

        # Start the service
        await self._start()

        # Wait forever for the stop event to be set
        await self.stop_event.wait()
