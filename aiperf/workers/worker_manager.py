import uuid
import asyncio
import logging
import time
import random
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

from ..common.base_manager import BaseManager
from ..common.models import TimingCredit, Conversation, ConversationTurn
from ..config.config_models import (
    WorkerConfig,
    EndpointConfig,
    EndpointSelectionStrategy,
    AuthConfig,
)
from ..common.communication import Communication
from .concrete_worker import ConcreteWorker
from ..api.clients import ClientFactory


class WorkerManager(BaseManager):
    """Worker manager for AIPerf.

    Responsible for managing workers, including:
    - Starting and stopping workers
    - Allocating credits to workers
    - Load balancing across endpoints
    - Implementing endpoint selection strategies
    """

    def __init__(
        self,
        config: WorkerConfig,
        communication: Optional[Communication] = None,
        component_id: Optional[str] = None,
    ):
        """Initialize the worker manager.

        Args:
            config: Worker configuration
            communication: Communication interface
            component_id: Optional component ID
        """
        super().__init__(
            component_id=component_id or f"worker_manager_{uuid.uuid4().hex[:8]}",
            config=config.__dict__,
        )
        self.worker_config = config
        self.communication = communication
        self._workers: Dict[str, ConcreteWorker] = {}
        self._idle_workers: Set[str] = set()
        self._active_workers: Set[str] = set()
        self._worker_lock = asyncio.Lock()
        self._is_initialized = False
        self._next_endpoint_index = 0
        self._running = False
        self._pending_credits: Dict[str, TimingCredit] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._scale_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None

        # Stats
        self._total_requests = 0
        self._total_responses = 0
        self._total_errors = 0
        self._total_successes = 0
        self._total_failures = 0
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None

        # Dataset manager reference - initialize as None
        self.dataset_manager = None

        # These will be loaded from system controller during initialization
        self.endpoints = []
        self.selection_strategy = None

    async def initialize(self) -> bool:
        """Initialize the worker manager.

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing worker manager")

        try:
            # Get endpoints from system controller via communication
            if self.communication:
                # Set up communication
                self.logger.info("Subscribing to timing.credit.issued")
                await self.communication.subscribe(
                    "timing.credit.issued", self._handle_timing_credit
                )
                self.logger.info("Subscribed to timing.credit.issued")
                await self.communication.subscribe(
                    "worker.request", self._handle_worker_request
                )

                # Subscribe to the system responses targeted to this component
                response_topic = f"system.response.{self.component_id}"
                await self.communication.subscribe(
                    response_topic, self._handle_system_response
                )

                # Request endpoints and selection strategy from system controller
                success = await self.communication.publish(
                    "system.request",
                    {"command": "get_worker_config", "source": self.component_id},
                )

                if success:
                    # Wait for the config to be received via the response handler
                    for _ in range(10):  # Try for 5 seconds (10 * 0.5)
                        if self.endpoints:
                            break
                        await asyncio.sleep(0.5)

                    if not self.endpoints:
                        self.logger.error("Timeout waiting for endpoint configuration")
                        # Set up a default endpoint for testing
                        self._setup_default_endpoint()
                else:
                    self.logger.error("Failed to send worker configuration request")
                    self._setup_default_endpoint()
            else:
                self.logger.warning(
                    "No communication interface available, skipping endpoint retrieval"
                )
                self._setup_default_endpoint()

            self._is_initialized = True
            self._is_ready = True
            self.logger.info(
                f"Worker manager initialized with {len(self.endpoints)} endpoints"
            )
            return True
        except Exception as e:
            self.logger.error(f"Error initializing worker manager: {e}")
            return False

    def _setup_default_endpoint(self):
        """Set up a default endpoint for testing purposes."""
        from ..config.config_models import EndpointConfig, AuthConfig

        self.endpoints = [
            EndpointConfig(
                name="test_endpoint",
                url="http://localhost:8000",
                api_type="openai",
                headers={"Content-Type": "application/json"},
                auth=AuthConfig(api_key="test"),
                timeout=30.0,
            )
        ]
        self.selection_strategy = EndpointSelectionStrategy.ROUND_ROBIN

    async def _handle_system_response(self, message: Dict[str, Any]) -> None:
        """Handle response from system controller.

        Args:
            message: Response message
        """
        try:
            data = message.get("data", {})
            if not data:
                self.logger.warning("Received empty system response")
                return

            # Check if this is a worker config response
            endpoint_config = data.get("endpoint_config")
            if endpoint_config:
                # Convert endpoint config dict to object
                from ..config.config_models import EndpointConfig, AuthConfig

                # Parse auth config if exists
                auth_config = None
                if "auth" in endpoint_config and endpoint_config["auth"]:
                    auth_data = endpoint_config["auth"]
                    auth_config = AuthConfig(**auth_data)

                # Remove auth dict and replace with auth config object
                endpoint_config_copy = endpoint_config.copy()
                endpoint_config_copy["auth"] = auth_config

                # Create endpoint config
                self.endpoints = [EndpointConfig(**endpoint_config_copy)]
                self.selection_strategy = EndpointSelectionStrategy.ROUND_ROBIN
                self.logger.info(
                    f"Got endpoint configuration: {self.endpoints[0].name}"
                )
        except Exception as e:
            self.logger.error(f"Error handling system response: {e}")
            # Try to set up a default endpoint if this fails
            self._setup_default_endpoint()

    async def _create_worker(self) -> Optional[ConcreteWorker]:
        """Create a new worker.

        Returns:
            Worker instance or None if creation failed
        """
        try:
            # Select endpoint for this worker
            endpoint = await self._select_endpoint()

            if not endpoint:
                self.logger.error("Failed to select endpoint for worker")
                return None

            # Create worker ID
            worker_id = f"worker_{uuid.uuid4().hex[:8]}"

            self.logger.debug(
                f"Creating worker {worker_id} for endpoint {endpoint.name}"
            )

            # Create worker instance
            worker = ConcreteWorker(endpoint_config=endpoint, component_id=worker_id)

            # Initialize worker
            self.logger.debug(f"Initializing worker {worker_id}")
            success = await worker.initialize()
            if not success:
                self.logger.error(f"Failed to initialize worker: {worker_id}")
                return None

            self.logger.info(
                f"Created worker: {worker_id} for endpoint: {endpoint.name}"
            )
            return worker
        except Exception as e:
            self.logger.error(f"Error creating worker: {e}")
            return None

    async def _select_endpoint(self) -> EndpointConfig:
        """Select an endpoint based on the selection strategy.

        Returns:
            Selected endpoint configuration
        """
        if self.selection_strategy == EndpointSelectionStrategy.ROUND_ROBIN:
            endpoint = self.endpoints[self._next_endpoint_index]
            self._next_endpoint_index = (self._next_endpoint_index + 1) % len(
                self.endpoints
            )
            return endpoint
        elif self.selection_strategy == EndpointSelectionStrategy.RANDOM:
            import random

            return random.choice(self.endpoints)
        elif self.selection_strategy == EndpointSelectionStrategy.WEIGHTED:
            import random

            weights = [endpoint.weight for endpoint in self.endpoints]
            return random.choices(self.endpoints, weights=weights, k=1)[0]
        else:
            # Default to round robin
            endpoint = self.endpoints[self._next_endpoint_index]
            self._next_endpoint_index = (self._next_endpoint_index + 1) % len(
                self.endpoints
            )
            return endpoint

    async def ready_check(self) -> bool:
        """Check if the worker manager is ready.

        Returns:
            True if the worker manager is ready, False otherwise
        """
        return self._is_initialized and self._is_ready

    async def publish_identity(self) -> bool:
        """Publish the worker manager's identity.

        Returns:
            True if identity was published successfully, False otherwise
        """
        if not self.communication:
            self.logger.warning(
                "No communication interface available, skipping identity publication"
            )
            return False

        try:
            identity = {
                "component_id": self.component_id,
                "component_type": "worker_manager",
                "workers_count": len(self._workers),
                "idle_workers": len(self._idle_workers),
                "active_workers": len(self._active_workers),
                "endpoints": [e.name for e in self.endpoints],
                "selection_strategy": self.selection_strategy.name,
            }

            success = await self.communication.publish("system.identity", identity)
            if success:
                self.logger.info("Published worker manager identity")
            else:
                self.logger.warning("Failed to publish worker manager identity")

            return success
        except Exception as e:
            self.logger.error(f"Error publishing worker manager identity: {e}")
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown the worker manager and all workers.

        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down worker manager")

        try:
            # Stop running
            await self.stop()

            # Shut down all workers
            async with self._worker_lock:
                for worker_id, worker in self._workers.items():
                    await worker.shutdown()

                self._workers.clear()
                self._idle_workers.clear()
                self._active_workers.clear()

            self._is_shutdown = True
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down worker manager: {e}")
            return False

    async def handle_command(
        self, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a command from the system controller.

        Args:
            command: Command string
            payload: Optional command payload

        Returns:
            Response dictionary with results
        """
        response = {"status": "error", "message": f"Unknown command: {command}"}

        if command == "start":
            success = await self.start()
            if success:
                response = {"status": "success", "message": "Worker manager started"}
            else:
                response = {
                    "status": "error",
                    "message": "Failed to start worker manager",
                }

        elif command == "stop":
            success = await self.stop()
            if success:
                response = {"status": "success", "message": "Worker manager stopped"}
            else:
                response = {
                    "status": "error",
                    "message": "Failed to stop worker manager",
                }

        elif command == "get_stats":
            stats = await self.get_stats()
            response = {"status": "success", "stats": stats}

        elif command == "scale":
            count = payload.get("count") if payload else None
            success = await self.scale_workers(count)
            if success:
                response = {
                    "status": "success",
                    "message": f"Scaled workers to {len(self._workers)}",
                }
            else:
                response = {"status": "error", "message": "Failed to scale workers"}

        return response

    async def _handle_timing_credit(self, message: Dict[str, Any]) -> None:
        """Handle timing credit message.

        Args:
            message: Message dictionary
        """
        try:
            # TimingManager publishes with { "credit": credit.__dict__, "credit_id": ..., "manager_id": ... }
            credit_data = message.get("credit")
            if not credit_data:
                self.logger.warning("Timing credit message missing credit data")
                return

            # Log the full message for debugging
            self.logger.info(f"Received timing credit message: {message}")

            # Convert credit data to TimingCredit
            credit = TimingCredit(
                credit_id=credit_data.get("credit_id"),
                scheduled_time=credit_data.get("scheduled_time"),
                issued_time=credit_data.get("issued_time", time.time()),
                metadata=credit_data.get("metadata", {}),
                worker_id=credit_data.get("worker_id"),
            )

            # Log receipt of credit
            self.logger.info(
                f"Processing timing credit: {credit.credit_id}, scheduled for: {credit.scheduled_time}"
            )

            # Process credit
            await self.process_credit(credit)
        except Exception as e:
            self.logger.error(f"Error handling timing credit: {e}")

    async def _handle_worker_request(self, message: Dict[str, Any]) -> None:
        """Handle worker request message.

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
                self.logger.warning("Worker request missing source")
                return

            # Process request
            response = await self.handle_command(command, payload)

            # Send response
            await self.communication.publish(f"worker.response.{source}", response)
        except Exception as e:
            self.logger.error(f"Error handling worker request: {e}")

    async def start(self) -> bool:
        """Start the worker manager.

        Returns:
            True if the worker manager started successfully, False otherwise
        """
        if self._running:
            self.logger.warning("Worker manager already running")
            return True

        try:
            self._running = True
            self._start_time = time.time()

            # Start background tasks
            self._worker_task = asyncio.create_task(self._process_workers())
            self._scale_task = asyncio.create_task(self._scale_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            # Announce worker manager start
            if self.communication:
                await self.communication.publish(
                    "worker.events",
                    {
                        "event": "worker_manager_started",
                        "timestamp": self._start_time,
                        "manager_id": self.component_id,
                    },
                )

            self.logger.info("Worker manager started")
            return True
        except Exception as e:
            self.logger.error(f"Error starting worker manager: {e}")
            self._running = False
            return False

    async def stop(self) -> bool:
        """Stop the worker manager.

        Returns:
            True if the worker manager stopped successfully, False otherwise
        """
        if not self._running:
            self.logger.warning("Worker manager not running")
            return True

        try:
            self._running = False
            self._stop_time = time.time()

            # Cancel background tasks
            for task in [self._worker_task, self._scale_task, self._keepalive_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Announce worker manager stop
            if self.communication:
                await self.communication.publish(
                    "worker.events",
                    {
                        "event": "worker_manager_stopped",
                        "timestamp": self._stop_time,
                        "manager_id": self.component_id,
                        "stats": await self.get_stats(),
                    },
                )

            self.logger.info("Worker manager stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping worker manager: {e}")
            return False

    async def process_credit(self, credit: TimingCredit) -> bool:
        """Process a timing credit.

        Args:
            credit: Timing credit

        Returns:
            True if the credit was processed successfully, False otherwise
        """
        if not self._running:
            self.logger.warning("Cannot process credit: worker manager not running")
            return False

        try:
            # Store credit for processing
            self._pending_credits[credit.credit_id] = credit
            self.logger.debug(
                f"Stored credit {credit.credit_id} for processing (pending: {len(self._pending_credits)})"
            )

            # Try to process immediately if idle workers are available
            await self._process_pending_credits()

            return True
        except Exception as e:
            self.logger.error(f"Error processing credit: {e}")
            return False

    async def _process_pending_credits(self) -> None:
        """Process pending credits."""
        # Get idle worker
        worker = await self.get_idle_worker()
        if not worker:
            idle_count = len(self._idle_workers)
            total_count = len(self._workers)
            self.logger.debug(
                f"No idle workers available (idle: {idle_count}, total: {total_count}, pending credits: {len(self._pending_credits)})"
            )
            return

        # Get next credit
        credit_id = next(iter(self._pending_credits), None)
        if not credit_id:
            self.logger.debug("No pending credits to process")
            return

        credit = self._pending_credits.pop(credit_id)
        self.logger.debug(
            f"Processing credit {credit.credit_id} with worker {worker.component_id}"
        )

        # Process credit with worker
        asyncio.create_task(self._process_credit_with_worker(worker, credit))

    async def _process_credit_with_worker(
        self, worker: ConcreteWorker, credit: TimingCredit
    ) -> None:
        """Process a credit with a worker.

        Args:
            worker: Worker to process the credit with
            credit: Timing credit to process
        """
        try:
            # Get conversation data for the credit
            conversation_data = {}

            # Check if dataset_manager exists and has the get_conversation method
            if not hasattr(self, "dataset_manager") or self.dataset_manager is None:
                self.logger.warning(
                    "Dataset manager not available - using default conversation data"
                )
                # Create empty conversation with default data
                conversation = {
                    "conversation_id": f"gen_{str(uuid.uuid4())}",
                    "metadata": {"generated": True},
                }

                # Prepare default conversation data
                conversation_data = await self._prepare_conversation_data(conversation)

                # Mark credit as being processed
                credit.worker_id = worker.component_id

                # Log the processing attempt
                self.logger.info(
                    f"Processing credit {credit.credit_id} with worker {worker.component_id}, using default conversation data"
                )

                # Process the credit with the worker
                try:
                    # Set timeout to prevent stuck workers
                    processing_task = asyncio.create_task(
                        worker.process_credit(credit, conversation_data)
                    )

                    # Wait for result with timeout
                    result = await asyncio.wait_for(
                        processing_task,
                        timeout=self.worker_config.worker_timeout or 30.0,
                    )

                    if result:
                        self.logger.info(
                            f"Worker {worker.component_id} successfully processed credit {credit.credit_id}"
                        )
                        self._total_successes += 1
                    else:
                        self.logger.warning(
                            f"Worker {worker.component_id} returned None for credit {credit.credit_id}"
                        )
                        self._total_failures += 1

                except asyncio.TimeoutError:
                    self.logger.error(
                        f"Timeout processing credit {credit.credit_id} with worker {worker.component_id}"
                    )
                    self._total_failures += 1
                except Exception as e:
                    self.logger.error(
                        f"Error processing credit with worker {worker.component_id}: {e}"
                    )
                    self._total_failures += 1

                return

            # If we have a dataset manager, continue with standard processing
            elif (
                self.dataset_manager
                and hasattr(self.dataset_manager, "get_conversation")
                and credit.metadata
                and "index" in credit.metadata
            ):
                # Get conversation from dataset manager
                try:
                    conversation_index = credit.metadata.get("index")
                    self.logger.debug(
                        f"Getting conversation at index {conversation_index}"
                    )

                    conversation = await self.dataset_manager.get_conversation(
                        conversation_index
                    )

                    if not conversation:
                        self.logger.warning(
                            f"No conversation found for index {conversation_index}"
                        )
                        # Create empty conversation if none found
                        conversation = {
                            "conversation_id": f"gen_{str(uuid.uuid4())}",
                            "metadata": {"generated": True},
                        }

                    self.logger.debug(
                        f"Got conversation: {conversation.get('conversation_id', 'unknown')}"
                    )

                    # Mark credit as being processed
                    credit.worker_id = worker.component_id

                    # Prepare conversation data
                    conversation_data = await self._prepare_conversation_data(
                        conversation
                    )

                    # Log the processing attempt
                    self.logger.info(
                        f"Processing credit {credit.credit_id} with worker {worker.component_id}, conversation: {conversation_data.get('conversation_id', 'unknown')}"
                    )

                    # Process the credit with the worker
                    try:
                        # Set timeout to prevent stuck workers
                        processing_task = asyncio.create_task(
                            worker.process_credit(credit, conversation_data)
                        )

                        # Wait for result with timeout
                        result = await asyncio.wait_for(
                            processing_task,
                            timeout=self.worker_config.worker_timeout or 30.0,
                        )

                        if result:
                            self.logger.info(
                                f"Worker {worker.component_id} successfully processed credit {credit.credit_id}"
                            )
                            self._total_successes += 1
                        else:
                            self.logger.warning(
                                f"Worker {worker.component_id} returned None for credit {credit.credit_id}"
                            )
                            self._total_failures += 1

                    except asyncio.TimeoutError:
                        self.logger.error(
                            f"Timeout processing credit {credit.credit_id} with worker {worker.component_id}"
                        )
                        self._total_failures += 1
                    except Exception as e:
                        self.logger.error(
                            f"Error processing credit with worker {worker.component_id}: {e}"
                        )
                        self._total_failures += 1

                except Exception as e:
                    self.logger.error(f"Error getting conversation data: {e}")
                    self._total_failures += 1
            else:
                self.logger.warning(
                    "Cannot get conversation data: dataset manager not available or credit missing index"
                )
                self._total_failures += 1

        except Exception as e:
            self.logger.error(f"Error processing credit: {e}")
            if hasattr(self, "_total_failures"):
                self._total_failures += 1

    async def _process_workers(self) -> None:
        """Background task for processing workers."""
        try:
            self.logger.info("Starting worker processor task")

            while self._running:
                # Process pending credits
                await self._process_pending_credits()

                # Short sleep to avoid busy wait
                await asyncio.sleep(0.01)

            self.logger.info("Worker processor task completed")
        except asyncio.CancelledError:
            self.logger.info("Worker processor task cancelled")
        except Exception as e:
            self.logger.error(f"Error in worker processor task: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get worker manager statistics.

        Returns:
            Dictionary with worker manager statistics
        """
        try:
            now = time.time()

            stats = {
                "workers_count": len(self._workers),
                "idle_workers": len(self._idle_workers),
                "active_workers": len(self._active_workers),
                "pending_credits": len(self._pending_credits),
                "total_requests": self._total_requests,
                "total_responses": self._total_responses,
                "total_errors": self._total_errors,
                "total_successes": self._total_successes,
                "total_failures": self._total_failures,
                "is_running": self._running,
                "elapsed_time": 0,
            }

            if self._start_time:
                end_time = self._stop_time if self._stop_time else now
                stats["start_time"] = self._start_time
                stats["elapsed_time"] = end_time - self._start_time

                if stats["elapsed_time"] > 0:
                    stats["requests_per_second"] = (
                        stats["total_requests"] / stats["elapsed_time"]
                    )
                    stats["responses_per_second"] = (
                        stats["total_responses"] / stats["elapsed_time"]
                    )
                    stats["error_rate"] = (
                        stats["total_errors"] / max(1, stats["total_requests"]) * 100
                    )

            return stats
        except Exception as e:
            self.logger.error(f"Error getting worker manager stats: {e}")
            return {"error": str(e)}

    async def scale_workers(self, target_count: Optional[int] = None) -> bool:
        """Scale the number of workers based on load or target count.

        Args:
            target_count: Optional target number of workers

        Returns:
            True if scaling was successful, False otherwise
        """
        try:
            async with self._worker_lock:
                current_count = len(self._workers)

                if target_count is not None:
                    # Scale to target count, bounded by min and max
                    target_count = max(
                        self.worker_config.min_workers,
                        min(target_count, self.worker_config.max_workers),
                    )
                else:
                    # Auto-scale based on pending credits
                    pending_count = len(self._pending_credits)
                    idle_count = len(self._idle_workers)

                    if (
                        pending_count > idle_count
                        and current_count < self.worker_config.max_workers
                    ):
                        # Scale up if we have pending credits and idle workers are insufficient
                        target_count = min(
                            current_count + pending_count - idle_count,
                            self.worker_config.max_workers,
                        )
                    elif (
                        idle_count > 2
                        and current_count > self.worker_config.min_workers
                    ):
                        # Scale down if we have excess idle workers
                        target_count = max(
                            current_count - (idle_count - 1),
                            self.worker_config.min_workers,
                        )
                    else:
                        # No need to scale
                        return True

                # Scale up
                if target_count > current_count:
                    for _ in range(target_count - current_count):
                        worker = await self._create_worker()
                        if worker:
                            self._workers[worker.component_id] = worker
                            self._idle_workers.add(worker.component_id)
                        else:
                            self.logger.warning(
                                "Failed to create worker during scaling"
                            )

                # Scale down (only idle workers)
                elif target_count < current_count:
                    to_remove = current_count - target_count
                    removed = 0

                    # Find idle workers to remove
                    idle_workers = list(self._idle_workers)
                    for worker_id in idle_workers[:to_remove]:
                        if worker_id in self._workers:
                            worker = self._workers.pop(worker_id)
                            self._idle_workers.discard(worker_id)
                            await worker.shutdown()
                            removed += 1

                    if removed < to_remove:
                        self.logger.warning(
                            f"Could only remove {removed} out of {to_remove} workers during scaling"
                        )

                self.logger.info(
                    f"Scaled workers from {current_count} to {len(self._workers)}"
                )
                return True
        except Exception as e:
            self.logger.error(f"Error scaling workers: {e}")
            return False

    async def _scale_loop(self) -> None:
        """Background task for auto-scaling workers."""
        try:
            self.logger.info("Starting worker auto-scaling task")

            while self._running:
                # Auto-scale workers
                await self.scale_workers()

                # Sleep for a while before checking again
                await asyncio.sleep(5.0)

            self.logger.info("Worker auto-scaling task completed")
        except asyncio.CancelledError:
            self.logger.info("Worker auto-scaling task cancelled")
        except Exception as e:
            self.logger.error(f"Error in worker auto-scaling task: {e}")

    async def _keepalive_loop(self) -> None:
        """Background task for checking worker health."""
        try:
            self.logger.info("Starting worker keepalive task")

            while self._running:
                # Check worker health
                async with self._worker_lock:
                    for worker_id, worker in list(self._workers.items()):
                        try:
                            healthy = await worker.keep_alive()
                            if not healthy:
                                self.logger.warning(
                                    f"Worker {worker_id} is unhealthy, removing"
                                )
                                self._workers.pop(worker_id)
                                self._idle_workers.discard(worker_id)
                                self._active_workers.discard(worker_id)
                                await worker.shutdown()
                        except Exception as e:
                            self.logger.error(f"Error checking worker health: {e}")

                # Sleep for a while before checking again
                await asyncio.sleep(self.worker_config.worker_keepalive_interval)

            self.logger.info("Worker keepalive task completed")
        except asyncio.CancelledError:
            self.logger.info("Worker keepalive task cancelled")
        except Exception as e:
            self.logger.error(f"Error in worker keepalive task: {e}")

    def set_dataset_manager(self, dataset_manager) -> None:
        """Set the dataset manager.

        Args:
            dataset_manager: Dataset manager instance
        """
        self.logger.info(f"Setting dataset manager: {dataset_manager}")
        self.dataset_manager = dataset_manager

    async def get_idle_worker(self) -> Optional[ConcreteWorker]:
        """Get an idle worker.

        Returns:
            Worker instance or None if no idle workers are available
        """
        try:
            async with self._worker_lock:
                if not self._idle_workers:
                    return None

                worker_id = next(iter(self._idle_workers))
                return self._workers.get(worker_id)
        except Exception as e:
            self.logger.error(f"Error getting idle worker: {e}")
            return None

    async def initialize_local_workers(self, count: int) -> bool:
        """Initialize the specified number of local workers.

        Args:
            count: Number of workers to initialize

        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing {count} local workers")

        if not self.endpoints:
            self.logger.error("No endpoints available for worker initialization")
            return False

        try:
            # Create specified number of workers
            successful_workers = 0
            for i in range(count):
                self.logger.debug(f"Creating worker {i + 1} of {count}")
                worker = await self._create_worker()
                if worker:
                    self._workers[worker.component_id] = worker
                    self._idle_workers.add(worker.component_id)
                    successful_workers += 1
                    self.logger.debug(
                        f"Worker {i + 1} created successfully: {worker.component_id}"
                    )
                else:
                    self.logger.error(f"Failed to create worker {i + 1}")
                    # Continue anyway to create as many workers as possible

            worker_count = len(self._workers)
            self.logger.info(
                f"Initialized {worker_count} local workers successfully out of {count} requested"
            )

            # Consider initialization successful if we were able to create at least one worker
            return worker_count > 0
        except Exception as e:
            self.logger.error(f"Error initializing local workers: {e}")
            return False

    def _extract_prompt_from_conversation(self, conversation: Dict[str, Any]) -> str:
        """Extract a prompt from a conversation.

        Args:
            conversation: Conversation dictionary

        Returns:
            Prompt text
        """
        # Try to get the last turn's request content
        turns = conversation.get("turns", [])
        if not turns:
            # Generate a simple default prompt
            return "Tell me something interesting about artificial intelligence."

        # Get the last turn
        last_turn = turns[-1]

        # Handle different formats
        if isinstance(last_turn, dict):
            # Try different known formats
            if "request" in last_turn:
                return last_turn.get("request", "")
            elif "request_data" in last_turn:
                request_data = last_turn.get("request_data", {})
                if isinstance(request_data, dict):
                    return request_data.get("prompt", {}).get("content", "")
                return str(request_data)

        # Fallback to a default prompt
        return "Tell me something interesting."

    def _convert_turns_to_messages(
        self, turns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert conversation turns to a list of messages for API requests.

        Args:
            turns: List of conversation turns

        Returns:
            List of messages
        """
        messages = []

        for turn in turns:
            if isinstance(turn, dict):
                # Add user message
                user_content = ""
                if "request" in turn:
                    user_content = turn.get("request", "")
                elif "request_data" in turn:
                    request_data = turn.get("request_data", {})
                    if isinstance(request_data, dict) and "prompt" in request_data:
                        user_content = request_data.get("prompt", {}).get("content", "")
                    else:
                        user_content = str(request_data)

                if user_content:
                    messages.append({"role": "user", "content": user_content})

                # Add assistant message if available
                assistant_content = ""
                if "response" in turn:
                    assistant_content = turn.get("response", "")
                elif "response_data" in turn:
                    response_data = turn.get("response_data", {})
                    if isinstance(response_data, dict):
                        assistant_content = response_data.get("content", "")
                    else:
                        assistant_content = str(response_data)

                if assistant_content:
                    messages.append({"role": "assistant", "content": assistant_content})

        # If no messages were created, add a default system message
        if not messages:
            messages.append(
                {"role": "system", "content": "You are a helpful assistant."}
            )

        return messages

    async def _prepare_conversation_data(
        self, conversation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare conversation data for worker processing.

        Args:
            conversation: Conversation data

        Returns:
            Processed conversation data ready for worker
        """
        # Extract prompt and build messages
        prompt = ""
        messages = []

        # Check if we have turns in the conversation
        turns = conversation.get("turns", [])

        if turns:
            # Process turns into messages
            for turn in turns:
                # Check if this is a dict (likely from __dict__ serialization)
                if isinstance(turn, dict):
                    # Add user message from request_data or request
                    if "request_data" in turn and turn["request_data"]:
                        request_data = turn["request_data"]
                        if isinstance(request_data, dict) and "prompt" in request_data:
                            prompt_data = request_data["prompt"]
                            content = (
                                prompt_data.get("content", "")
                                if isinstance(prompt_data, dict)
                                else str(prompt_data)
                            )
                            messages.append({"role": "user", "content": content})
                            # Store the last user message as the prompt
                            prompt = content
                    elif "request" in turn:
                        content = turn["request"]
                        messages.append({"role": "user", "content": content})
                        # Store the last user message as the prompt
                        prompt = content

                    # Add assistant message from response_data or response
                    if "response_data" in turn and turn["response_data"]:
                        response_data = turn["response_data"]
                        if (
                            isinstance(response_data, dict)
                            and "content" in response_data
                        ):
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": response_data["content"],
                                }
                            )
                        else:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": str(response_data),
                                }
                            )
                    elif "response" in turn:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": turn["response"],
                            }
                        )

        # If no messages were created and we have a metadata field, check for default prompts
        if not messages and "metadata" in conversation:
            metadata = conversation.get("metadata", {})
            if "default_prompt" in metadata:
                prompt = metadata["default_prompt"]
                messages.append({"role": "user", "content": prompt})

        # If still no messages, create a default system message and prompt
        if not messages:
            default_prompt = (
                "Tell me something interesting about artificial intelligence."
            )
            prompt = default_prompt
            messages.append({"role": "user", "content": default_prompt})
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
            )

        # Build the final conversation data
        conversation_data = {
            "conversation_id": conversation.get("conversation_id"),
            "metadata": conversation.get("metadata", {}),
            "prompt": prompt,
            "messages": messages,
            "model": "gpt-3.5-turbo",  # Default model
            "temperature": 0.7,
            "max_tokens": 1024,
        }

        self.logger.debug(f"Prepared conversation data with {len(messages)} messages")
        return conversation_data
