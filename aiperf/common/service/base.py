import asyncio
import contextlib
import logging
import signal
import uuid
from abc import ABC, abstractmethod
from typing import Optional, TypeVar

from rich.console import Console
from rich.logging import RichHandler

from aiperf.common.comms.communication import BaseCommunication
from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    ServiceState,
    ServiceType,
    Topic,
    ClientType,
)
from aiperf.common.models.messages import (
    BaseMessage,
    HeartbeatMessage,
    RegistrationMessage,
    MessageT,
)

# Type variable for message types
M = TypeVar("M", bound=BaseMessage)

# Create a central console object for rich logging
_console = Console()


def get_logger(name: str) -> logging.Logger:
    """Get a logger configured with rich for colored output.

    Args:
        name: The name for the logger

    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if it hasn't been configured yet
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=True,
            console=_console,
            tracebacks_show_locals=True,
        )
        logger.addHandler(handler)

    return logger


class ServiceBase(ABC):
    """Base class for all AIPerf services, providing common functionality for communication,
    state management, and lifecycle operations.

    This class provides the foundation for implementing the various components of the AIPerf system,
    such as the System Controller, Dataset Manager, Timing Manager, Worker Manager, etc.
    """

    def __init__(self, service_config: ServiceConfig, service_id: str = None):
        self.service_id: str = service_id or uuid.uuid4().hex
        self.service_config = service_config
        self.logger = get_logger(self.__class__.__name__)
        self.logger.debug(
            f"Initializing service {self.service_id} {self.service_type} {self.__class__.__name__}"
        )
        self.state: ServiceState = ServiceState.UNKNOWN
        self.heartbeat_task = None
        self.heartbeat_interval = (
            self.service_config.heartbeat_interval
        )  # Default interval in seconds
        self.stop_event = asyncio.Event()
        self.communication: Optional[BaseCommunication] = None
        # Set to store signal handler tasks
        self._signal_tasks = set()

    @property
    @abstractmethod
    def service_type(self) -> ServiceType:
        """The type of service."""
        pass

    async def _base_init(self) -> None:
        """Initialize the service communication and signal handlers.

        This method should be called by derived classes to initialize the service.
        """
        await asyncio.sleep(0.1)  # Allow time for the event loop to start

        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Initialize the service
        self.state = ServiceState.INITIALIZING

        # Initialize communication unless explicitly skipped
        if not self.communication:
            self.communication = CommunicationFactory.create_communication(
                self.service_config
            )

            # Initialize the communication instance
            if self.communication:
                success = await self.communication.initialize()
                if not success:
                    self.logger.error(
                        f"Failed to initialize {self.service_config.comm_backend} communication"
                    )
                    self.state = ServiceState.ERROR
                    return

    async def _publish_message(
        self, client_type: ClientType, topic: Topic, message: BaseMessage
    ) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish

        Returns:
            True if published successfully
        """
        if not self.communication:
            self.logger.warning("Cannot publish: Communication is not initialized")
            return False

        self.logger.debug(f"Publishing message to topic {topic}: {message}")

        success = await self.communication.publish(client_type, topic, message)
        if not success:
            self.logger.error(f"Failed to publish message to topic {topic}")
        return success

    async def _send_heartbeat(self) -> None:
        """Send a heartbeat message to the system controller."""
        heartbeat_message = self.wrap_message(HeartbeatMessage())
        self.logger.debug("Sending heartbeat message: %s", heartbeat_message)
        await self._publish_message(
            ClientType.COMPONENT_PUB, Topic.HEARTBEAT, heartbeat_message
        )

    async def _set_service_status(self, status: ServiceState) -> None:
        """Set the status of the service."""
        self.state = status

    async def _start_heartbeat_task(self) -> None:
        """Start a background task to send heartbeats at regular intervals."""

        async def heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeat()

        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        self.logger.debug(
            "Started heartbeat task with interval %ss", self.heartbeat_interval
        )

    async def _register(self) -> None:
        """Register the service with the system controller.

        This method should be called after the service has been initialized and is ready to
        start processing messages.
        """
        self.logger.debug(
            "Attempting to register service %s (%s) with system controller",
            self.service_type,
            self.service_id,
        )
        await self._publish_message(
            ClientType.COMPONENT_PUB,
            Topic.REGISTRATION,
            self.wrap_message(RegistrationMessage()),
        )

    @abstractmethod
    async def run(self) -> None:
        """Run the service.

        This method should be implemented by derived classes to run the main loop of the service.
        """
        pass

    def wrap_message(self, message: MessageT) -> MessageT:
        """Wrap a message of the given type with the given payload.
        Pre-fills the service_id and service_type.

        Args:
            message: The message to wrap
        """
        message.service_id = self.service_id
        message.service_type = self.service_type
        return message

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        def signal_handler(sig: int) -> None:
            # Create a task and store it so it doesn't get garbage collected
            task = asyncio.create_task(self._handle_signal(sig))
            # Store the task somewhere to prevent it from being garbage collected
            # before it completes
            self._signal_tasks.add(task)
            task.add_done_callback(self._signal_tasks.discard)

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        # self.logger.debug("Signal handlers set up for graceful shutdown")

    async def _handle_signal(self, sig: int) -> None:
        """Handle received signals by triggering graceful shutdown.

        Args:
            sig: The signal number received
        """
        sig_name = signal.Signals(sig).name
        self.logger.debug(f"Received signal {sig_name}, initiating graceful shutdown")

        # Stop the service if it's running
        if self.state == ServiceState.RUNNING:
            await self.stop()
        else:
            # Just set the stop event to break out of the run loop
            self.stop_event.set()

    async def _start(self) -> None:
        """Start the service and its components.

        This method should be called to start the service after it has been initialized.
        """
        self.logger.debug("Starting service %s", self.service_id)
        await self._set_service_status(ServiceState.STARTING)
        try:
            await self._on_start()
            await self._set_service_status(ServiceState.RUNNING)
        except BaseException as e:
            self.logger.exception(
                "Failed to start service %s: %s", self.service_type, self.service_id
            )
            await self._set_service_status(ServiceState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop the service and clean up its components."""
        if self.state != ServiceState.RUNNING:
            self.logger.warning(
                "Service %s is not running, cannot stop", self.service_type
            )
            return
        await self._set_service_status(ServiceState.STOPPING)
        # Signal the run method to exit if it hasn't already
        self.stop_event.set()

        # Cancel heartbeat task if running
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.heartbeat_task

        await self._on_stop()

        # Shutdown communication component
        if self.communication:
            success = await self.communication.shutdown()
            if not success:
                self.logger.warning("Failed to properly shutdown communication")

        await self._cleanup()

        self.state = ServiceState.STOPPED

    ################################################################################
    ## Abstract methods to be implemented by derived classes
    ################################################################################

    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize service-specific components.

        This method should be implemented by derived classes to set up any resources
        specific to that service.
        """

    @abstractmethod
    async def _on_start(self) -> None:
        """Start the service.

        This method should be implemented by derived classes to run any processes
        or components specific to that service.
        """

    @abstractmethod
    async def _on_stop(self) -> None:
        """Stop the service.

        This method should be implemented by derived classes to stop any processes
        or components specific to that service.
        """

    @abstractmethod
    async def _cleanup(self) -> None:
        """Clean up service-specific components.

        This method should be implemented by derived classes to free any resources
        allocated by the service.
        """
