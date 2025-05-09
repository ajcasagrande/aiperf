import asyncio
import contextlib
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from aiperf.common.comms.communication import Communication
from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceRunType, ServiceState, ServiceType, Topic
from aiperf.common.models.messages import (
    BaseMessage,
    HeartbeatMessage,
    RegistrationMessage,
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
        service_type: ServiceType,
        config: ServiceConfig,
        autostart: bool = False,
    ):
        self.service_id: str = uuid.uuid4().hex
        self.service_type: ServiceType = service_type
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(
            f"Initializing service {self.service_id} {self.service_type.value} {self.__class__.__name__}"
        )
        self.state: ServiceState = ServiceState.UNKNOWN
        self.heartbeat_task = None
        self.heartbeat_interval = 10  # Default interval in seconds
        self.stop_event = asyncio.Event()
        self.autostart = autostart
        self.communication: Optional[Communication] = None
        # Flag to allow system controller to handle its own communication initialization
        self._skip_parent_comm_init = False

    async def _subscribe_to_topic(self, topic: Topic) -> None:
        """Subscribe to a topic for receiving messages.

        Args:
            topic: The topic to subscribe to

        """
        if not self.communication:
            self.logger.warning("Cannot subscribe: Communication is not initialized")
            return

        topic_str = topic.value
        self.logger.debug(f"Subscribing to topic {topic_str}")

        async def message_callback(data: Dict[str, Any]) -> None:
            message = BaseMessage.model_validate(data)
            await self._process_message(topic, message)

        success = await self.communication.subscribe(topic_str, message_callback)
        if not success:
            self.logger.error(f"Failed to subscribe to topic {topic_str}")
        else:
            self.logger.debug(f"Successfully subscribed to topic {topic_str}")

    async def _publish_message(self, topic: Topic, message: BaseMessage) -> None:
        """Publish a message to a topic."""
        if not self.communication:
            self.logger.warning("Cannot publish: Communication is not initialized")
            return

        topic_str = topic.value
        self.logger.debug(f"Publishing message to topic {topic_str}: {message}")

        success = await self.communication.publish(topic_str, message)
        if not success:
            self.logger.error(f"Failed to publish message to topic {topic_str}")

    async def _send_heartbeat(self) -> None:
        """Send a heartbeat message to the system controller."""
        heartbeat_message = HeartbeatMessage(
            service_id=self.service_id,
            service_type=self.service_type,
        )
        self.logger.debug("Sending heartbeat message: %s", heartbeat_message)
        await self._publish_message(Topic.HEARTBEAT, heartbeat_message)

    async def _set_service_status(self, status: ServiceState) -> None:
        """Send a service state message to the system controller."""
        self.state = status
        status_message = StatusMessage(
            service_id=self.service_id,
            service_type=self.service_type,
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

    async def _register(self) -> None:
        """Register the service with the system controller.

        This method should be called after the service has been initialized and is ready to
        start processing messages.
        """
        self.logger.debug("Registering service with system controller")
        await self._publish_message(
            Topic.REGISTRATION,
            RegistrationMessage(
                service_id=self.service_id,
                service_type=self.service_type,
            ),
        )

    async def run(self) -> None:
        """Start the service and initialize its components."""
        try:
            # Initialize the service
            self.state = ServiceState.INITIALIZING

            # Initialize communication unless explicitly skipped
            if not self.communication and not self._skip_parent_comm_init:
                comm_type = self.config.comm_backend.value
                if self.config.service_run_type == ServiceRunType.ASYNC:
                    comm_type = "memory"
                elif self.config.service_run_type == ServiceRunType.MULTIPROCESSING:
                    comm_type = "zmq"
                self.communication = CommunicationFactory.create_communication(
                    comm_type=comm_type
                )

                # Initialize the communication instance
                if self.communication:
                    success = await self.communication.initialize()
                    if not success:
                        self.logger.error(
                            f"Failed to initialize {comm_type} communication"
                        )
                        self.state = ServiceState.ERROR
                        return

            await self._initialize()

            # Set up communication subscriptions if communication is available
            # Subscribe to common topics
            await self._subscribe_to_topic(Topic.COMMAND)

            # Additional service-specific subscriptions can be added in derived classes

            await self._register()
            # Start heartbeat task
            await self._start_heartbeat_task()
            await self._set_service_status(ServiceState.READY)

            # Start the service if it is set to auto start.
            # Otherwise, wait for the System Controller to start it
            if self.autostart:
                await self._start()

            # Wait forever for the stop event to be set
            await self.stop_event.wait()
        except asyncio.exceptions.CancelledError:
            self.logger.debug("Service execution cancelled")
        except BaseException:
            self.logger.exception("Service execution failed:")
            await self._set_service_status(ServiceState.ERROR)
        finally:
            # Make sure to clean up properly even if there was an error
            await self.stop()

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
            self.logger.exception("Failed to start service %s: %s", self.service_id, e)
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

        This method should be implemented by derived classes to clean up any resources
        specific to that service.
        """

    @abstractmethod
    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        This method should be implemented by derived classes to handle messages
        received from other services in the system.
        """
