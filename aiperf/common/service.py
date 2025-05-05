import asyncio
import contextlib
import logging
import uuid
from abc import ABC, abstractmethod

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceState, Topic
from aiperf.common.models.messages import (
    BaseMessage,
    HeartbeatMessage,
    StatusMessage,
)


class ServiceBase(ABC):
    """Base class for all AIPerf services, providing common functionality for communication,
    state management, and lifecycle operations.

    This class provides the foundation for implementing the various components of the AIPerf system,
    such as the System Controller, Dataset Manager, Timing Manager, Worker Manager, etc.
    """

    def __init__(
        self,
        service_type: str,
        config: ServiceConfig,
    ):
        self.service_id: str = uuid.uuid4().hex
        self.service_type: str = service_type
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(
            f"Initializing service {self.service_id} {self.service_type} {self.__class__.__name__}"
        )
        self.state: ServiceState = ServiceState.UNKNOWN
        self.heartbeat_task = None
        self.heartbeat_interval = 10  # Default interval in seconds
        self.stop_event = asyncio.Event()

    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize service-specific components.

        This method should be implemented by derived classes to set up any resources
        specific to that service.
        """

    @abstractmethod
    async def _run(self) -> None:
        """Run the service.

        This method should be implemented by derived classes to run any processes
        or components specific to that service.
        """

    @abstractmethod
    async def _stop(self) -> None:
        """Stop the service.

        This method should be implemented by derived classes to stop any processes
        or components specific to that service.
        """

    @abstractmethod
    async def _cleanup(self) -> None:
        """Clean up service-specific components.

        This method should be implemented by derived classes to clean up any resources
        specific to that service.
        """

    @abstractmethod
    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        This method should be implemented by derived classes to handle messages
        received from other services in the system.
        """

    async def _subscribe_to_topic(self, topic: Topic) -> None:
        """Subscribe to a topic for receiving messages.

        Args:
            topic: The topic to subscribe to

        """
        # TODO: Implement the subscription logic internally here

    async def _publish_message(self, topic: Topic, message: BaseMessage) -> None:
        """Publish a message to a topic."""
        # TODO: implement the internal publish against the comms library

    async def _send_heartbeat(self) -> None:
        """Send a heartbeat message to the system controller."""
        heartbeat_message = HeartbeatMessage(
            service_id=self.service_id,
            service_type=self.config.service_type,
        )
        self.logger.debug("Sending heartbeat message: %s", heartbeat_message)
        await self._publish_message(Topic.HEARTBEAT, heartbeat_message)

    async def _set_service_status(self, status: ServiceState) -> None:
        """Send a service state message to the system controller."""
        self.state = status
        if status not in [ServiceState.INITIALIZING]:
            status_message = StatusMessage(
                service_id=self.service_id,
                service_type=self.config.service_type,
                state=self.state,
            )
            await self._publish_message(Topic.STATUS, status_message)

    async def _start_heartbeat_task(self) -> None:
        """Start a background task to send heartbeats at regular intervals."""

        async def heartbeat_loop() -> None:
            while True:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)

        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        self.logger.debug(
            "Started heartbeat task with interval %ss", self.heartbeat_interval
        )

    async def run(self) -> None:
        """Start the service and initialize its components."""
        try:
            # Initialize the service
            await self._set_service_status(ServiceState.INITIALIZING)
            await self._initialize()
            # Start heartbeat task
            await self._start_heartbeat_task()
            await self._set_service_status(ServiceState.RUNNING)
            # Start the service
            await self._run()

            # Keep the service running until stop_event is set
            if not self.stop_event.is_set():
                await self.stop_event.wait()
        except asyncio.exceptions.CancelledError:
            self.logger.debug("Service execution cancelled")
        except BaseException:
            self.logger.exception("Service execution failed:")
            await self._set_service_status(ServiceState.ERROR)
        finally:
            # Make sure to clean up properly even if there was an error
            await self.stop()

    async def stop(self) -> None:
        """Stop the service and clean up its components."""
        await self._set_service_status(ServiceState.STOPPING)
        # Signal the run method to exit
        self.stop_event.set()

        # Cancel heartbeat task if running
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.heartbeat_task

        await self._stop()
        await self._cleanup()
        await self._set_service_status(ServiceState.STOPPED)


def bootstrap_and_run_service(
    service_type: type[ServiceBase], config: ServiceConfig | None = None
):
    """Bootstrap the service and run it.

    This function will load the service configuration, create an instance of the service,
    and run it.

    Args:
        service_type: The class of the service to run
        config: The service configuration to use, if not provided, the service configuration
                will be loaded from the config file

    """
    import uvloop

    uvloop.install()

    # Load the service configuration
    if config is None:
        from aiperf.common.config.loader import load_service_config

        config = load_service_config()

    service = service_type(config=config)
    uvloop.run(service.run())
