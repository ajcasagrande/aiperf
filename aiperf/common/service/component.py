import asyncio
from abc import ABC

from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, ServiceState, ClientType, Topic
from aiperf.common.models.messages import CommandMessage
from aiperf.common.service.base import ServiceBase


class ComponentServiceBase(ServiceBase, ABC):
    """Base class for all component services.
    This class provides a common interface for all component services in the AIPerf framework.
    It inherits from the ServiceBase class and implements the required methods for component
    services.
    """

    def __init__(self, service_type: ServiceType, config: ServiceConfig) -> None:
        super().__init__(service_type=service_type, config=config)

    async def run(self) -> None:
        """Start the service and initialize its components."""
        try:
            await asyncio.sleep(0.1)  # Allow time for the event loop to start
            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # Initialize the service
            self.state = ServiceState.INITIALIZING

            # Initialize communication unless explicitly skipped
            if not self.communication:
                self.communication = CommunicationFactory.create_communication(
                    comm_type=self.config.comm_backend
                )

                # Initialize the communication instance
                if self.communication:
                    success = await self.communication.initialize()
                    if not success:
                        self.logger.error(
                            f"Failed to initialize {self.config.comm_backend} communication"
                        )
                        self.state = ServiceState.ERROR
                        return

            await self._initialize()

            # Set up communication subscriptions if communication is available
            # Subscribe to common topics
            await self._subscribe_to_topic(
                ClientType.CONTROLLER_SUB, Topic.COMMAND, CommandMessage
            )

            # Additional service-specific subscriptions can be added in derived classes

            await self._register()
            # Start heartbeat task
            await self._start_heartbeat_task()
            await self._set_service_status(ServiceState.READY)

            # Wait forever for the stop event to be set
            await self.stop_event.wait()
        except asyncio.exceptions.CancelledError:
            self.logger.debug("Service execution cancelled")
        except BaseException:
            self.logger.exception("Service execution failed:")
            await self._set_service_status(ServiceState.ERROR)
        finally:
            # Make sure to clean up properly even if there was an error
            if self.state == ServiceState.RUNNING:
                await self.stop()
