import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from ..common.base_manager import BaseComponent
from ..common.models import SystemState
from ..config.config_models import AIperfConfig
from .kubernetes_manager import KubernetesManager


class SystemController(BaseComponent):
    """System controller for AIPerf.

    Responsible for orchestrating all components, ensuring they are ready
    and healthy, and managing the lifecycle of the system.
    """

    def __init__(self, config: AIperfConfig):
        """Initialize the system controller.

        Args:
            config: AIPerf configuration
        """
        super().__init__(
            component_id=f"system_controller_{uuid.uuid4().hex[:8]}",
            config=config.__dict__,
        )
        self.aiperf_config = config
        self.components: Dict[str, BaseComponent] = {}
        self.state = SystemState.INITIALIZING
        self.start_time = time.time()
        self.ready_components: Set[str] = set()
        self._shutdown_event = asyncio.Event()
        self._kubernetes_manager = None
        self._workers_registry: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> bool:
        """Initialize the system controller and all components.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing system controller")

        # Register communication channel
        # This would be implemented with actual communication mechanism

        # Initialize Kubernetes manager if enabled
        if self.aiperf_config.kubernetes.enabled:
            try:
                self._kubernetes_manager = KubernetesManager(self.aiperf_config)
                self.logger.info("Kubernetes support enabled")
            except ImportError:
                self.logger.error(
                    "Failed to import KubernetesManager. Is the kubernetes package installed?"
                )
                return False

        # Start bringup sequence
        try:
            await self._start_components()
            self.state = SystemState.READY
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            self.state = SystemState.ERROR
            return False

    async def _start_components(self) -> bool:
        """Start all system components.

        Returns:
            True if all components started successfully, False otherwise
        """
        # Create communication interface for component interaction
        from ..common.communication_factory import CommunicationFactory

        comm_type = self.aiperf_config.communication.type
        communication = CommunicationFactory.create_communication(
            comm_type, **self.aiperf_config.communication.parameters
        )

        if not communication:
            self.logger.error(
                f"Failed to create communication interface of type: {comm_type}"
            )
            return False

        # Initialize communication
        if not await communication.initialize():
            self.logger.error("Failed to initialize communication interface")
            return False

        # Set up communication for system controller FIRST
        # so workers can request information
        self.communication = communication
        await self.communication.subscribe(
            "system.request", self._handle_system_request
        )

        # If Kubernetes is enabled and we're in the controller pod,
        # we only need to start the central components.
        # Workers will be managed by Kubernetes.
        if self.aiperf_config.kubernetes.enabled:
            self.logger.info("Starting components with Kubernetes integration")

            # Start only controller-side components
            # 1. Dataset Manager
            from ..dataset.dataset_manager import DatasetManager

            dataset_manager = DatasetManager(self.aiperf_config.dataset, communication)
            if not await dataset_manager.initialize():
                self.logger.error("Failed to initialize dataset manager")
                return False
            await self.register_component(dataset_manager)

            # 2. Timing Manager
            from ..timing.timing_manager import TimingManager

            timing_manager = TimingManager(self.aiperf_config.timing, communication)
            if not await timing_manager.initialize():
                self.logger.error("Failed to initialize timing manager")
                return False
            await self.register_component(timing_manager)

            # 3. Records Manager
            from ..records.records_manager import RecordsManager

            records_manager = RecordsManager(self.aiperf_config.metrics, communication)
            if not await records_manager.initialize():
                self.logger.error("Failed to initialize records manager")
                return False
            await self.register_component(records_manager)

            # 4. Post Processors
            from ..processors.post_processors import PostProcessorRegistry

            post_processor_registry = PostProcessorRegistry(
                self.aiperf_config.metrics, communication
            )
            if not await post_processor_registry.initialize():
                self.logger.error("Failed to initialize post processor registry")
                return False
            await self.register_component(post_processor_registry)

            # Worker Manager is still needed but only manages worker connections
            from ..workers.worker_manager import WorkerManager

            worker_manager = WorkerManager(self.aiperf_config.workers, communication)
            if not await worker_manager.initialize():
                self.logger.error("Failed to initialize worker manager")
                return False
            await self.register_component(worker_manager)

            # Publish component identities for discovery
            for component in self.components.values():
                if hasattr(component, "publish_identity"):
                    await component.publish_identity()
        else:
            # Start components in the traditional non-Kubernetes mode
            self.logger.info("Starting components in non-Kubernetes mode")

            # 1. Dataset Manager
            from ..dataset.dataset_manager import DatasetManager

            dataset_manager = DatasetManager(self.aiperf_config.dataset, communication)
            if not await dataset_manager.initialize():
                self.logger.error("Failed to initialize dataset manager")
                return False
            await self.register_component(dataset_manager)

            # 2. Timing Manager
            from ..timing.timing_manager import TimingManager

            timing_manager = TimingManager(self.aiperf_config.timing, communication)
            if not await timing_manager.initialize():
                self.logger.error("Failed to initialize timing manager")
                return False
            await self.register_component(timing_manager)

            # 3. Worker Manager (includes local worker initialization)
            from ..workers.worker_manager import WorkerManager

            worker_manager = WorkerManager(self.aiperf_config.workers, communication)
            if not await worker_manager.initialize():
                self.logger.error("Failed to initialize worker manager")
                return False
            await self.register_component(worker_manager)

            # 4. Records Manager
            from ..records.records_manager import RecordsManager

            records_manager = RecordsManager(self.aiperf_config.metrics, communication)
            if not await records_manager.initialize():
                self.logger.error("Failed to initialize records manager")
                return False
            await self.register_component(records_manager)

            # 5. Post Processors
            from ..processors.post_processors import PostProcessorRegistry

            post_processor_registry = PostProcessorRegistry(
                self.aiperf_config.metrics, communication
            )
            if not await post_processor_registry.initialize():
                self.logger.error("Failed to initialize post processor registry")
                return False
            await self.register_component(post_processor_registry)

            # Initialize required number of local workers
            if not await worker_manager.initialize_local_workers(
                self.aiperf_config.workers.min_workers
            ):
                self.logger.error("Failed to initialize local workers")
                return False

            # Publish component identities for discovery
            for component in self.components.values():
                if hasattr(component, "publish_identity"):
                    await component.publish_identity()

        self.logger.info("All components started successfully")
        return True

    async def _handle_system_request(self, message: Dict[str, Any]) -> None:
        """Handle system request message.

        Args:
            message: Message dictionary
        """
        if not self.communication:
            return

        try:
            command = message.get("command")
            payload = message.get("payload", {})
            source = message.get("source")

            if not source:
                self.logger.warning("System request missing source")
                return

            # Process request
            response = await self.handle_command(command, payload)

            # Send response
            await self.communication.publish(f"system.response.{source}", response)
        except Exception as e:
            self.logger.error(f"Error handling system request: {e}")

    async def ready_check(self) -> bool:
        """Check if all components are ready.

        Returns:
            True if all components are ready, False otherwise
        """
        if self.state != SystemState.READY:
            return False

        # Check readiness of all components
        all_ready = True
        for component_id, component in self.components.items():
            is_ready = await component.ready_check()
            if not is_ready:
                all_ready = False
                self.logger.warning(f"Component not ready: {component_id}")
            else:
                self.ready_components.add(component_id)

        return all_ready

    async def start_profile(self) -> bool:
        """Start profiling run.

        Returns:
            True if profile started successfully, False otherwise
        """
        if self.state != SystemState.READY:
            self.logger.error(
                f"Cannot start profile: system not ready (state={self.state})"
            )
            return False

        self.logger.info("Starting profile")

        # If using Kubernetes, scale worker deployment to desired count
        if self.aiperf_config.kubernetes.enabled and self._kubernetes_manager:
            try:
                # Scale workers to min_workers
                await self._kubernetes_manager.scale_workers(
                    self.aiperf_config.workers.min_workers
                )
                self.logger.info(
                    f"Scaled Kubernetes workers to {self.aiperf_config.workers.min_workers}"
                )
            except Exception as e:
                self.logger.error(f"Error scaling Kubernetes workers: {e}")
                # Continue anyway

        # Start all required components for profiling
        try:
            # 1. Start worker manager
            worker_manager = None
            for component_id, component in self.components.items():
                if component_id.startswith("worker_manager"):
                    worker_manager = component
                    break

            if worker_manager:
                self.logger.info("Starting worker manager")
                if hasattr(worker_manager, "start"):
                    success = await worker_manager.start()
                    if not success:
                        self.logger.error("Failed to start worker manager")
                        return False
                    else:
                        self.logger.info("Worker manager started successfully")
            else:
                self.logger.error("No worker manager found")
                return False

            # 2. Start timing manager to generate timing credits
            timing_manager = None
            for component_id, component in self.components.items():
                if component_id.startswith("timing_manager"):
                    timing_manager = component
                    break

            if timing_manager:
                self.logger.info("Starting timing manager")
                if hasattr(timing_manager, "start_timing"):
                    success = await timing_manager.start_timing()
                    if not success:
                        self.logger.error("Failed to start timing manager")
                        return False
                    else:
                        self.logger.info("Timing manager started successfully")
            else:
                self.logger.error("No timing manager found")
                return False

            self.state = SystemState.RUNNING
            return True

        except Exception as e:
            self.logger.error(f"Error starting profile: {e}")
            return False

    async def stop_profile(self) -> bool:
        """Stop profiling run.

        Returns:
            True if profile stopped successfully, False otherwise
        """
        if self.state != SystemState.RUNNING:
            self.logger.warning(
                f"Cannot stop profile: system not running (state={self.state})"
            )
            return False

        self.logger.info("Stopping profile")

        try:
            # 1. Stop timing manager first
            timing_manager = None
            for component_id, component in self.components.items():
                if component_id.startswith("timing_manager"):
                    timing_manager = component
                    break

            if timing_manager:
                self.logger.info("Stopping timing manager")
                if hasattr(timing_manager, "stop_timing"):
                    success = await timing_manager.stop_timing()
                    if not success:
                        self.logger.error("Failed to stop timing manager")
                        # Continue anyway
                    else:
                        self.logger.info("Timing manager stopped successfully")

            # 2. Stop worker manager after timing manager
            worker_manager = None
            for component_id, component in self.components.items():
                if component_id.startswith("worker_manager"):
                    worker_manager = component
                    break

            if worker_manager:
                self.logger.info("Stopping worker manager")
                if hasattr(worker_manager, "stop"):
                    success = await worker_manager.stop()
                    if not success:
                        self.logger.error("Failed to stop worker manager")
                        # Continue anyway
                    else:
                        self.logger.info("Worker manager stopped successfully")

            self.state = SystemState.READY
            return True
        except Exception as e:
            self.logger.error(f"Error stopping profile: {e}")
            # Set state to READY even if there was an error to allow restarting
            self.state = SystemState.READY
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown all components.

        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down system")

        if self.state == SystemState.RUNNING:
            await self.stop_profile()

        self.state = SystemState.STOPPING

        # Shutdown all registered components
        shutdown_success = True
        for component_id, component in self.components.items():
            try:
                self.logger.info(f"Shutting down component: {component_id}")
                if hasattr(component, "shutdown"):
                    success = await component.shutdown()
                    if not success:
                        self.logger.error(
                            f"Failed to shut down component: {component_id}"
                        )
                        shutdown_success = False
            except Exception as e:
                self.logger.error(f"Error shutting down component {component_id}: {e}")
                shutdown_success = False

        # If using Kubernetes and we're in controller mode, scale workers to 0
        if self.aiperf_config.kubernetes.enabled and self._kubernetes_manager:
            try:
                await self._kubernetes_manager.scale_workers(0)
                self.logger.info("Scaled Kubernetes workers to 0")
            except Exception as e:
                self.logger.error(f"Error scaling down Kubernetes workers: {e}")

        # Shutdown communication if it exists
        if hasattr(self, "communication") and self.communication:
            try:
                self.logger.info("Shutting down communication")
                await self.communication.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down communication: {e}")
                shutdown_success = False

        # Add a small delay to ensure all async operations complete
        await asyncio.sleep(0.5)

        self._is_shutdown = True
        self.state = SystemState.STOPPED
        self._shutdown_event.set()
        return shutdown_success

    async def wait_for_shutdown(self) -> None:
        """Wait for system shutdown."""
        await self._shutdown_event.wait()

    def get_status(self) -> Dict[str, Any]:
        """Get system status.

        Returns:
            Dictionary with system status information
        """
        status = {
            "state": self.state.name,
            "uptime": time.time() - self.start_time,
            "ready_components": list(self.ready_components),
            "total_components": len(self.components),
            "is_ready": self.state == SystemState.READY,
            "is_running": self.state == SystemState.RUNNING,
            "kubernetes_enabled": self.aiperf_config.kubernetes.enabled,
        }

        # Add Kubernetes status if enabled
        if self.aiperf_config.kubernetes.enabled and self._kubernetes_manager:
            try:
                k8s_status = asyncio.run_coroutine_threadsafe(
                    self._kubernetes_manager.get_status(), asyncio.get_running_loop()
                ).result()
                status["kubernetes"] = k8s_status
            except Exception as e:
                status["kubernetes"] = {"error": str(e)}

        return status

    async def register_component(self, component: BaseComponent) -> bool:
        """Register a component with the system controller.

        Args:
            component: Component to register

        Returns:
            True if registration was successful, False otherwise
        """
        if component.component_id in self.components:
            self.logger.warning(
                f"Component already registered: {component.component_id}"
            )
            return False

        self.components[component.component_id] = component
        self.logger.info(f"Registered component: {component.component_id}")
        return True

    async def register_worker(
        self, worker_id: str, data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a worker with the system controller.

        Args:
            worker_id: Worker ID
            data: Optional worker data

        Returns:
            True if registration was successful, False otherwise
        """
        self._workers_registry[worker_id] = {
            "registered_at": time.time(),
            "last_heartbeat": time.time(),
            "data": data or {},
        }
        self.logger.info(f"Registered worker: {worker_id}")
        return True

    async def get_worker_config(self) -> Dict[str, Any]:
        """Get worker configuration.

        This is called by workers during initialization in Kubernetes mode.

        Returns:
            Worker configuration dictionary
        """
        # Select an endpoint for the worker based on selection strategy
        endpoint = None

        if self.aiperf_config.endpoint_selection == "ROUND_ROBIN":
            # Implement round-robin selection
            # This is a simplified version
            if self.aiperf_config.endpoints:
                endpoint = self.aiperf_config.endpoints[0]
        elif self.aiperf_config.endpoint_selection == "RANDOM":
            # Implement random selection
            import random

            if self.aiperf_config.endpoints:
                endpoint = random.choice(self.aiperf_config.endpoints)
        else:
            # Default to first endpoint
            if self.aiperf_config.endpoints:
                endpoint = self.aiperf_config.endpoints[0]

        if not endpoint:
            return {"error": "No endpoints available"}

        # Return worker configuration
        return {
            "status": "success",
            "endpoint_config": endpoint.__dict__,
            "worker_config": self.aiperf_config.workers.__dict__,
        }

    async def handle_command(
        self, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle commands from components or external systems.

        Args:
            command: Command to execute
            payload: Command payload

        Returns:
            Response dictionary
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}

        if command == "get_status":
            response = {"status": "success", "data": self.get_status()}
        elif command == "get_worker_config":
            config = await self.get_worker_config()
            if "error" in config:
                response = {"status": "error", "message": config["error"]}
            else:
                response = {
                    "status": "success",
                    "endpoint_config": config["endpoint_config"],
                }
        elif command == "register_worker":
            worker_id = payload.get("worker_id") if payload else None
            if not worker_id:
                response = {"status": "error", "message": "Missing worker_id"}
            else:
                success = await self.register_worker(worker_id, payload)
                if success:
                    response = {
                        "status": "success",
                        "message": f"Worker {worker_id} registered",
                    }
                else:
                    response = {
                        "status": "error",
                        "message": f"Failed to register worker {worker_id}",
                    }

        return response
