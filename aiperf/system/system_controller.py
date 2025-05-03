import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from ..common.base_manager import BaseComponent
from ..common.models import SystemState
from ..config.config_models import AIperfConfig

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
        super().__init__(component_id=f"system_controller_{uuid.uuid4().hex[:8]}", config=config.__dict__)
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
                from .kubernetes_manager import KubernetesManager
                self._kubernetes_manager = KubernetesManager(self.aiperf_config)
                self.logger.info("Kubernetes support enabled")
            except ImportError:
                self.logger.error("Failed to import KubernetesManager. Is the kubernetes package installed?")
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
        # If Kubernetes is enabled and we're in the controller pod,
        # we only need to start the central components.
        # Workers will be managed by Kubernetes.
        if self.aiperf_config.kubernetes.enabled:
            self.logger.info("Starting components with Kubernetes integration")
            # Start only controller-side components
            # Workers will connect independently via worker_cli.py
        else:
            # Start components in the traditional non-Kubernetes mode
            # 1. Dataset Manager
            # 2. Timing Manager
            # 3. Worker Manager
            # 4. Records Manager
            # 5. Post Processors
            pass
        
        # This is a placeholder - actual implementation would register 
        # and initialize the actual component instances
        
        self.logger.info("All components started")
        return True
        
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
            self.logger.error(f"Cannot start profile: system not ready (state={self.state})")
            return False
            
        self.logger.info("Starting profile")
        
        # If using Kubernetes, scale worker deployment to desired count
        if self.aiperf_config.kubernetes.enabled and self._kubernetes_manager:
            try:
                # Scale workers to min_workers
                await self._kubernetes_manager.scale_workers(self.aiperf_config.workers.min_workers)
                self.logger.info(f"Scaled Kubernetes workers to {self.aiperf_config.workers.min_workers}")
            except Exception as e:
                self.logger.error(f"Error scaling Kubernetes workers: {e}")
                # Continue anyway
        
        # Notify all components to start profiling
        # In practice, this would send commands to all the components
        
        self.state = SystemState.RUNNING
        return True
        
    async def stop_profile(self) -> bool:
        """Stop profiling run.
        
        Returns:
            True if profile stopped successfully, False otherwise
        """
        if self.state != SystemState.RUNNING:
            self.logger.warning(f"Cannot stop profile: system not running (state={self.state})")
            return False
            
        self.logger.info("Stopping profile")
        
        # Notify all components to stop profiling
        # In practice, this would send commands to all the components
        
        self.state = SystemState.READY
        return True
    
    async def shutdown(self) -> bool:
        """Gracefully shutdown all components.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down system")
        
        if self.state == SystemState.RUNNING:
            await self.stop_profile()
            
        self.state = SystemState.STOPPING
        
        # Notify all components to shut down
        # In practice, this would send commands to all the components and wait for confirmation
        
        # If using Kubernetes and we're in controller mode, scale workers to 0
        if self.aiperf_config.kubernetes.enabled and self._kubernetes_manager:
            try:
                await self._kubernetes_manager.scale_workers(0)
                self.logger.info("Scaled Kubernetes workers to 0")
            except Exception as e:
                self.logger.error(f"Error scaling down Kubernetes workers: {e}")
        
        self._is_shutdown = True
        self.state = SystemState.STOPPED
        self._shutdown_event.set()
        return True
        
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
            "kubernetes_enabled": self.aiperf_config.kubernetes.enabled
        }
        
        # Add Kubernetes status if enabled
        if self.aiperf_config.kubernetes.enabled and self._kubernetes_manager:
            try:
                k8s_status = asyncio.run_coroutine_threadsafe(
                    self._kubernetes_manager.get_status(),
                    asyncio.get_running_loop()
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
            self.logger.warning(f"Component already registered: {component.component_id}")
            return False
            
        self.components[component.component_id] = component
        self.logger.info(f"Registered component: {component.component_id}")
        return True

    async def register_worker(self, worker_id: str, data: Optional[Dict[str, Any]] = None) -> bool:
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
            "data": data or {}
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
            "endpoint_config": endpoint.__dict__,
            "worker_config": self.aiperf_config.workers.__dict__
        }
        
    async def handle_command(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle commands from components or external systems.
        
        Args:
            command: Command to execute
            payload: Command payload
            
        Returns:
            Response dictionary
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}
        
        if command == "get_status":
            response = {
                "status": "success",
                "data": self.get_status()
            }
        elif command == "get_worker_config":
            config = await self.get_worker_config()
            if "error" in config:
                response = {
                    "status": "error",
                    "message": config["error"]
                }
            else:
                response = {
                    "status": "success",
                    "endpoint_config": config["endpoint_config"]
                }
        elif command == "register_worker":
            worker_id = payload.get("worker_id") if payload else None
            if not worker_id:
                response = {
                    "status": "error",
                    "message": "Missing worker_id"
                }
            else:
                success = await self.register_worker(worker_id, payload)
                if success:
                    response = {
                        "status": "success",
                        "message": f"Worker {worker_id} registered"
                    }
                else:
                    response = {
                        "status": "error",
                        "message": f"Failed to register worker {worker_id}"
                    }
        
        return response
