import asyncio
import sys
from typing import Any

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import Topic
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase
from aiperf.services.dataset_manager.main import DatasetManager
from aiperf.services.timing_manager.main import TimingManager


class SystemController(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type="system_controller", config=config)
        self.services: dict[str, Any] = {}

    async def _initialize(self) -> None:
        """Initialize system controller-specific components."""
        self.logger.debug("Initializing System Controller")

    async def _run(self) -> None:
        """Start the system controller and launch required services."""
        self.logger.debug("Starting System Controller")
        await self._start_all_services()

    async def _start_all_services(self) -> None:
        """Start all required services."""
        self.logger.debug("Starting all required services")
        # TODO: Implement starting of all services
        await self._start_service_in_process(
            "dataset_manager", DatasetManager, self.config
        )
        await self._start_service_in_process(
            "timing_manager", TimingManager, self.config
        )

    async def _start_service_in_process(
        self, service_name: str, service_class: type[ServiceBase], config: ServiceConfig
    ) -> None:
        """Start a service in a separate process.

        Args:
            service_name: The name of the service
            service_class: The service class to instantiate
            config: The configuration for the service
        """
        import multiprocessing

        def run_service(service_cls, service_config):
            from aiperf.common.service import bootstrap_and_run_service

            bootstrap_and_run_service(service_cls, config=service_config)

        self.logger.info(f"Starting service {service_name} in a new process")
        process = multiprocessing.Process(
            target=run_service,
            args=(service_class, config),
            name=f"{service_name}_process",
        )
        process.daemon = True
        process.start()

        # Store the process reference
        self.services[service_name] = {
            "process": process,
            "config": config,
            "service_class": service_class,
        }
        self.logger.info(f"Service {service_name} started with PID {process.pid}")

    async def _stop_all_services(self) -> None:
        """Stop all required services."""
        self.logger.debug("Stopping all required services")
        # TODO: Implement stopping of all services
        for service_name, service_info in self.services.items():
            process = service_info["process"]
            process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(process.join), timeout=10.0)
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout waiting for service {service_name} to stop"
                )
                process.kill()
            self.logger.info(f"Service {service_name} stopped with PID {process.pid}")

    async def _stop(self) -> None:
        """Stop the system controller and all running services."""
        self.logger.debug("Stopping System Controller")
        await self._stop_all_services()

    async def _cleanup(self) -> None:
        """Clean up system controller-specific components."""
        self.logger.debug("Cleaning up System Controller")

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        self.logger.debug(f"Processing message in dataset manager: {topic}, {message}")


def main() -> None:
    from aiperf.common.service import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)


if __name__ == "__main__":
    sys.exit(main())
