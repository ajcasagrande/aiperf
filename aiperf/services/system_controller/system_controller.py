import sys
import uuid
from datetime import datetime
from typing import List

from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    CommandType,
    ServiceRegistrationStatus,
    ServiceRunType,
    ServiceState,
    ServiceType,
    Topic,
    ClientType,
)
from aiperf.common.exceptions.service import ServiceInitializationException
from aiperf.common.models.messages import (
    CommandMessage,
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.service.controller import ControllerServiceBase
from aiperf.services.system_controller.kubernetes_manager import (
    KubernetesServiceManager,
)
from aiperf.services.system_controller.multiprocess_manager import MultiProcessManager
from aiperf.services.system_controller.service_manager import (
    ServiceManagerBase,
    ServiceRunInfo,
)


class SystemController(ControllerServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.SYSTEM_CONTROLLER, config=config)

        # List of required service types, in the order they should be started
        self.required_service_types: List[ServiceType] = [
            ServiceType.DATASET_MANAGER,
            ServiceType.TIMING_MANAGER,
            ServiceType.WORKER_MANAGER,
            ServiceType.RECORDS_MANAGER,
            ServiceType.POST_PROCESSOR_MANAGER,
        ]

        self.service_manager: ServiceManagerBase = None

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

        if self.config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self.service_manager = MultiProcessManager(
                self.required_service_types, self.config
            )
        elif self.config.service_run_type == ServiceRunType.KUBERNETES:
            self.service_manager = KubernetesServiceManager(
                self.required_service_types, self.config
            )
        else:
            raise ValueError(
                f"Unsupported service run type: {self.config.service_run_type}"
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
        await self.communication.subscribe(
            ClientType.COMPONENT_SUB,
            Topic.REGISTRATION,
            self._process_registration_message,
        )
        await self.communication.subscribe(
            ClientType.COMPONENT_SUB, Topic.HEARTBEAT, self._process_heartbeat_message
        )
        await self.communication.subscribe(
            ClientType.COMPONENT_SUB, Topic.STATUS, self._process_status_message
        )

        self.logger.info(
            f"Successfully initialized communication with backend: {comm_type}"
        )

    async def _on_start(self) -> None:
        """Start the system controller and launch required services."""
        self.logger.debug("Starting System Controller")

        # Start all required services
        await self.service_manager.initialize_all_services()

        # Wait for all required services to be registered
        registered = await self.service_manager.wait_for_all_services_registration(
            self.stop_event
        )
        if self.stop_event.is_set():
            self.logger.info("System Controller stopped before all services registered")
            return  # Don't continue with the rest of the initialization
        if not registered:
            self.logger.error(
                "Not all required services registered within the timeout period"
            )
            raise ServiceInitializationException(
                "Not all required services registered within the timeout period"
            )
        else:
            self.logger.info("All required services registered successfully")

        # Wait for all required services to be started
        await self.start_all_services()
        await self.service_manager.wait_for_all_services_start()

    async def start_all_services(self) -> None:
        """Start all required services."""
        self.logger.debug("Starting services")
        for service_info in self.service_manager.service_id_map.values():
            if service_info.state == ServiceState.READY:
                await self.send_command_to_service(
                    target_service_id=service_info.service_id,
                    command=CommandType.START,
                )

    async def _on_stop(self) -> None:
        """Stop the system controller and all running services."""
        self.logger.debug("Stopping System Controller")
        await self.service_manager.stop_all_services()

    async def _cleanup(self) -> None:
        """Clean up system controller-specific components."""
        self.logger.debug("Cleaning up System Controller")
        # TODO: Additional cleanup if needed

    async def _process_registration_message(self, message: RegistrationMessage) -> None:
        """Process a registration message from a service.

        Args:
            message: The registration message to process
        """
        self.logger.warning(f"Processing registration message: {message}")
        service_id = message.service_id
        service_type = message.service_type

        self.logger.warning(
            f"Processing registration from {service_type} with ID: {service_id}"
        )

        self.logger.debug(
            f"Processing registration from {service_type} with ID: {service_id}"
        )

        service_info = ServiceRunInfo(
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_type=service_type,
            service_id=service_id,
            registration_time=datetime.now(),
            state=ServiceState.READY,
            last_heartbeat=datetime.now(),
        )

        self.service_manager.service_id_map[service_id] = service_info
        if service_type not in self.service_manager.service_map:
            self.service_manager.service_map[service_type] = []
        self.service_manager.service_map[service_type].append(service_info)

        is_required = service_type in self.required_service_types
        self.logger.info(
            f"Registered {'required' if is_required else 'non-required'} service: {service_type} with ID: {service_id}"
        )

        # Send configure command to the newly registered service
        success = await self.send_command_to_service(
            target_service_id=service_id, command=CommandType.CONFIGURE
        )
        if success:
            self.logger.debug(
                f"Sent configure command to {service_type} (ID: {service_id})"
            )
        else:
            self.logger.warning(
                f"Failed to send configure command to {service_type} (ID: {service_id})"
            )

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
        if service_id in self.service_manager.service_id_map:
            self.service_manager.service_id_map[service_id].last_heartbeat = timestamp
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
        if service_id in self.service_manager.service_id_map:
            self.service_manager.service_id_map[service_id].state = state
            self.logger.debug(f"Updated state for {service_id} to {state}")
        else:
            self.logger.warning(
                f"Received status update from unknown service: {service_id} ({service_type})"
            )

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
        return await self._publish_message(
            ClientType.CONTROLLER_PUB, Topic.COMMAND, command_message
        )


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)


if __name__ == "__main__":
    sys.exit(main())
