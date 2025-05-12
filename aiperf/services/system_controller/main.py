import asyncio
import sys
import uuid
from multiprocessing import Process
from typing import Any, Dict
from enum import Enum
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.comms.communication import Communication
from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    CommandType,
    ServiceRunType,
    ServiceType,
    Topic,
    ClientType,
)
from aiperf.common.exceptions.service import ServiceInitializationException
from aiperf.common.models.messages import (
    BaseMessage,
    CommandMessage,
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.service.controller import ControllerServiceBase
from aiperf.services.dataset_manager.main import DatasetManager
from aiperf.services.post_processor_manager.main import PostProcessorManager
from aiperf.services.records_manager.main import RecordsManager
from aiperf.services.timing_manager.main import TimingManager
from aiperf.services.worker_manager.main import WorkerManager


class ServiceRegistrationStatus(Enum):
    WAITING = "waiting"
    REGISTERED = "registered"
    TIMEOUT = "timeout"


class RequiredServiceRegistration(BaseModel):
    service_type: ServiceType
    status: ServiceRegistrationStatus = Field(default=ServiceRegistrationStatus.WAITING)
    service_id: str = Field(default="")
    registration_time: datetime = Field(default_factory=datetime.now)


class SystemController(ControllerServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.SYSTEM_CONTROLLER, config=config)
        self.services: dict[str, Any] = {}
        # Don't create communication in the parent class
        self._skip_parent_comm_init = True
        self.communication: Communication = None
        self.components: Dict[str, Any] = {}
        self.service_processes: Dict[str, Process] = {}

    async def _initialize(self) -> None:
        """Initialize system controller-specific components."""
        self.logger.debug("Initializing System Controller")

        # Initialize communication component based on config
        comm_type = self.config.comm_backend
        self.logger.info(f"Initializing communication with backend: {comm_type}")

        self.communication = CommunicationFactory.create_communication(
            comm_type=comm_type
        )

        if self.communication is None:
            self.logger.error(
                f"Failed to create communication with backend: {comm_type}"
            )
            raise ServiceInitializationException(
                f"Failed to initialize communication backend: {comm_type}"
            )

        # Initialize the communication
        success = await self.communication.initialize()
        if not success:
            self.logger.error("Failed to initialize communication")
            raise ServiceInitializationException("Failed to initialize communication")

        # Create clients
        await self.communication.create_clients(
            ClientType.COMPONENT_SUB,
            ClientType.CONTROLLER_PUB,
        )

        # Subscribe to relevant messages
        await self._subscribe_to_topic(ClientType.COMPONENT_SUB, Topic.REGISTRATION)
        await self._subscribe_to_topic(ClientType.COMPONENT_SUB, Topic.HEARTBEAT)
        await self._subscribe_to_topic(ClientType.COMPONENT_SUB, Topic.STATUS)

        self.logger.info(
            f"Successfully initialized communication with backend: {comm_type}"
        )

    async def _on_start(self) -> None:
        """Start the system controller and launch required services."""
        self.logger.debug("Starting System Controller")

        # Start all required services
        await self._initialize_all_services()

        # Wait for all required services to be registered
        registered = await self._wait_for_services_registration()
        if not registered:
            self.logger.error(
                "Not all required services registered within the timeout period"
            )
            raise ServiceInitializationException(
                "Not all required services registered within the timeout period"
            )

        self.logger.info("All required services registered successfully")

    async def _initialize_all_services(self) -> None:
        """Initialize all required services."""
        self.logger.debug("Initializing all required services")

        if self.config.service_run_type == ServiceRunType.MULTIPROCESSING:
            await self._start_all_services_multiprocessing()
        elif self.config.service_run_type == ServiceRunType.KUBERNETES:
            await self._start_all_services_kubernetes()
        else:
            raise ValueError(
                f"Unsupported service run type: {self.config.service_run_type}"
            )

    async def _stop_all_services(self) -> None:
        """Stop all required services."""
        self.logger.debug("Stopping all required services")

        if self.config.service_run_type == ServiceRunType.MULTIPROCESSING:
            await self._stop_all_services_multiprocessing()
        elif self.config.service_run_type == ServiceRunType.KUBERNETES:
            await self._stop_all_services_kubernetes()
        else:
            raise ValueError(
                f"Unsupported service run type: {self.config.service_run_type}"
            )

    async def _on_stop(self) -> None:
        """Stop the system controller and all running services."""
        self.logger.debug("Stopping System Controller")
        await self._stop_all_services()

        # Shutdown communication component
        if self.communication:
            success = await self.communication.shutdown()
            if not success:
                self.logger.warning("Failed to properly shutdown communication")

    async def _cleanup(self) -> None:
        """Clean up system controller-specific components."""
        self.logger.debug("Cleaning up System Controller")
        # TODO: Additional cleanup if needed

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(
            f"Processing message in System Controller: {topic}, {message}"
        )
        if topic == Topic.REGISTRATION:
            await self._process_registration_message(message)
        elif topic == Topic.HEARTBEAT:
            await self._process_heartbeat_message(message)
        elif topic == Topic.STATUS:
            await self._process_status_message(message)
        # TODO: Process other message types

    async def _process_registration_message(self, message: RegistrationMessage) -> None:
        """Process a registration message from a service.

        Args:
            message: The registration message to process
        """
        service_id = message.service_id
        service_type = message.service_type

        self.logger.debug(
            f"Processing registration from {service_type} with ID: {service_id}"
        )

        # Store the component information
        self.components[service_id] = type(
            "ServiceComponent",
            (),
            {
                "service_id": service_id,
                "service_type": service_type,
                "state": message.state,
                "last_heartbeat": message.timestamp,
            },
        )

        self.logger.info(f"Registered service: {service_type} with ID: {service_id}")

    async def _process_heartbeat_message(self, message: HeartbeatMessage) -> None:
        """Process a heartbeat message from a service.

        Args:
            message: The heartbeat message to process
        """
        service_id = message.service_id
        service_type = message.service_type
        timestamp = message.timestamp

        self.logger.debug(f"Received heartbeat from {service_type} (ID: {service_id})")

        # Update the last heartbeat timestamp if the component exists
        if service_id in self.components:
            self.components[service_id].last_heartbeat = timestamp
            self.logger.debug(f"Updated heartbeat for {service_id} to {timestamp}")
        else:
            self.logger.warning(
                f"Received heartbeat from unknown service: {service_id} ({service_type})"
            )

    async def _process_status_message(self, message: StatusMessage) -> None:
        """Process a status message from a service.

        Args:
            message: The status message to process
        """
        service_id = message.service_id
        service_type = message.service_type
        state = message.state

        self.logger.debug(
            f"Received status update from {service_type} (ID: {service_id}): {state}"
        )

        # Update the component state if the component exists
        if service_id in self.components:
            self.components[service_id].state = state
            self.logger.debug(f"Updated state for {service_id} to {state}")
        else:
            self.logger.warning(
                f"Received status update from unknown service: {service_id} ({service_type})"
            )

    async def _start_all_services_multiprocessing(self) -> None:
        """Start all required services as multiprocessing processes."""
        self.logger.debug("Starting all required services as multiprocessing processes")
        # TODO: better way to define these
        service_configs = [
            (ServiceType.DATASET_MANAGER, DatasetManager),
            (ServiceType.TIMING_MANAGER, TimingManager),
            (ServiceType.WORKER_MANAGER, WorkerManager),
            (ServiceType.RECORDS_MANAGER, RecordsManager),
            (ServiceType.POST_PROCESSOR_MANAGER, PostProcessorManager),
        ]

        # In multiprocessing mode, each process needs its own communication instance
        # Create and start all service processes
        for service_name, service_class in service_configs:
            # When using multiprocessing, we can't share the communication instance
            # Each process will create its own instance based on the config
            process = Process(
                target=bootstrap_and_run_service,
                name=f"{service_name}_process",
                args=(service_class, self.config),
                daemon=False,
            )
            process.start()
            # TODO: Implement a more robust way to track services, shared between the run types using ServiceRunInfo
            self.service_processes[service_name] = process
            self.logger.info(
                f"Service {service_name} started as process (pid: {process.pid})"
            )

    async def _stop_all_services_multiprocessing(self) -> None:
        """Stop all required services as multiprocessing processes."""
        self.logger.debug("Stopping all service processes")

        # First terminate all processes
        for service_name, process in self.service_processes.items():
            self.logger.info(f"Stopping {service_name} process (pid: {process.pid})")
            process.terminate()

        # Then wait for all to finish in parallel
        await asyncio.gather(
            *[
                self._wait_for_process(service_name, process)
                for service_name, process in self.service_processes.items()
            ]
        )

    async def _wait_for_process(self, service_name: str, process: Process) -> None:
        """Wait for a process to terminate with timeout handling."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(process.join, timeout=1.0),  # Add timeout to join
                timeout=5.0,  # Overall timeout
            )
            self.logger.info(f"{service_name} process stopped (pid: {process.pid})")
        except asyncio.TimeoutError:
            self.logger.warning(
                f"{service_name} process (pid: {process.pid}) did not terminate gracefully, killing"
            )
            process.kill()

    async def _start_all_services_kubernetes(self) -> None:
        """Start all required services as Kubernetes pods."""
        self.logger.debug("Starting all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError

    async def _stop_all_services_kubernetes(self) -> None:
        """Stop all required services as Kubernetes pods."""
        self.logger.debug("Stopping all required services as Kubernetes pods")
        # TODO: Implement Kubernetes
        raise NotImplementedError

    async def send_command_to_service(
        self, target_service_id: str, command: CommandType
    ) -> bool:
        """Send a command to a specific service.

        Args:
            target_service_id: ID of the target service
            command: The command to send (from CommandType enum)

        Returns:
            True if the command was sent successfully
        """
        if not self.communication:
            self.logger.error("Cannot send command: Communication is not initialized")
            return False

        # Create command message using the helper method
        command_message = CommandMessage.create(
            service_id=self.service_id,
            service_type=self.service_type,
            command_id=f"cmd_{uuid.uuid4().hex[:8]}",
            command_type=command,
            target_service_id=target_service_id,
        )

        # Publish command message
        return await self._publish_message(Topic.COMMAND, command_message)

    async def _wait_for_services_registration(self, timeout_seconds: int = 60) -> bool:
        """Wait for all required services to be registered.

        Args:
            timeout_seconds: Maximum time to wait in seconds

        Returns:
            True if all services registered successfully, False otherwise
        """
        self.logger.info("Waiting for all required services to register...")

        # Create list of required services based on the services we start
        required_services = [
            RequiredServiceRegistration(service_type=ServiceType.DATASET_MANAGER),
            RequiredServiceRegistration(service_type=ServiceType.TIMING_MANAGER),
            RequiredServiceRegistration(service_type=ServiceType.WORKER_MANAGER),
            RequiredServiceRegistration(service_type=ServiceType.RECORDS_MANAGER),
            RequiredServiceRegistration(
                service_type=ServiceType.POST_PROCESSOR_MANAGER
            ),
        ]

        # Create a map for faster lookups
        service_map = {service.service_type: service for service in required_services}

        # Set the deadline
        deadline = datetime.now() + timedelta(seconds=timeout_seconds)

        # Wait until all services are registered or timeout
        while datetime.now() < deadline:
            # Check if all services are registered
            all_registered = all(
                service.status == ServiceRegistrationStatus.REGISTERED
                for service in service_map.values()
            )

            if all_registered:
                self.logger.info("All required services registered successfully")
                return True

            # Update registration status from components dict
            for component_id, component in self.components.items():
                service_type = component.service_type
                if (
                    service_type in service_map
                    and service_map[service_type].status
                    == ServiceRegistrationStatus.WAITING
                ):
                    service_map[
                        service_type
                    ].status = ServiceRegistrationStatus.REGISTERED
                    service_map[service_type].service_id = component_id
                    service_map[service_type].registration_time = datetime.now()
                    self.logger.info(
                        f"Service {service_type} registered with ID: {component_id}"
                    )

            # Wait a bit before checking again
            await asyncio.sleep(0.5)

        # Log which services didn't register in time
        for service in service_map.values():
            if service.status != ServiceRegistrationStatus.REGISTERED:
                service.status = ServiceRegistrationStatus.TIMEOUT
                self.logger.warning(
                    f"Service {service.service_type} failed to register within timeout"
                )

        return False


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)


if __name__ == "__main__":
    sys.exit(main())
