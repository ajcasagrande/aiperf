#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
__init_subclass__ Approach

Automatically wraps specified methods when subclasses are defined.
Very powerful but can be more complex to understand.
"""

import asyncio
import logging
from functools import wraps
from typing import Any


class LifecycleState:
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class BaseService:
    """Base service that automatically wraps lifecycle methods in subclasses."""

    # Define which methods should be wrapped and their state transitions
    _LIFECYCLE_METHODS: dict[str, dict[str, str]] = {
        "initialize": {
            "from_state": LifecycleState.CREATED,
            "to_state": LifecycleState.INITIALIZED,
            "intermediate_state": LifecycleState.INITIALIZING,
        },
        "start": {
            "from_state": LifecycleState.INITIALIZED,
            "to_state": LifecycleState.RUNNING,
            "intermediate_state": LifecycleState.STARTING,
        },
        "stop": {
            "from_state": LifecycleState.RUNNING,
            "to_state": LifecycleState.STOPPED,
            "intermediate_state": LifecycleState.STOPPING,
        },
    }

    def __init_subclass__(cls, **kwargs):
        """Automatically wrap lifecycle methods when subclass is defined."""
        super().__init_subclass__(**kwargs)

        # Wrap each lifecycle method in the subclass
        for method_name, config in cls._LIFECYCLE_METHODS.items():
            if hasattr(cls, method_name):
                original_method = getattr(cls, method_name)
                wrapped_method = cls._create_lifecycle_wrapper(
                    original_method, method_name, config
                )
                setattr(cls, method_name, wrapped_method)

    @classmethod
    def _create_lifecycle_wrapper(
        cls, original_method, method_name: str, config: dict[str, str]
    ):
        """Create a wrapped version of a lifecycle method."""

        @wraps(original_method)
        async def wrapper(self, *args, **kwargs):
            # Pre-execution state validation
            if self._state != config["from_state"]:
                raise ValueError(
                    f"Cannot {method_name} from state {self._state}, "
                    f"expected {config['from_state']}"
                )

            # Transition to intermediate state
            self._state = config["intermediate_state"]
            self.logger.info(f"Starting {method_name}...")

            try:
                # Call the original method
                result = await original_method(self, *args, **kwargs)

                # Success - transition to final state
                self._state = config["to_state"]
                self.logger.info(f"{method_name.capitalize()} completed successfully")

                return result

            except Exception as e:
                # Error - transition to error state
                self._state = LifecycleState.ERROR
                self.logger.error(f"{method_name.capitalize()} failed: {e}")
                raise

        return wrapper

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._state = LifecycleState.CREATED

    # Default implementations (can be overridden)
    async def initialize(self) -> None:
        """Override in subclass to add initialization logic."""
        pass

    async def start(self) -> None:
        """Override in subclass to add start logic."""
        pass

    async def stop(self) -> None:
        """Override in subclass to add stop logic."""
        pass

    @property
    def state(self) -> str:
        return self._state


class MyService(BaseService):
    """
    Subclass with automatic method wrapping!
    Just define the methods - wrapping happens automatically.
    """

    def __init__(self, service_id: str):
        super().__init__(service_id)
        self.db_connection = None
        self.background_tasks = []

    async def initialize(self) -> None:
        """
        This method is automatically wrapped with lifecycle management.
        No decorators needed, no super() calls required!
        """
        self.logger.info("Connecting to database...")
        self.db_connection = await self._connect_database()
        self.logger.info("Database connection established")

    async def start(self) -> None:
        """Automatically wrapped - just implement business logic."""
        self.logger.info("Starting background workers...")

        for i in range(3):
            task = asyncio.create_task(self._background_worker(f"worker-{i}"))
            self.background_tasks.append(task)

        self.logger.info(f"Started {len(self.background_tasks)} background workers")

    async def stop(self) -> None:
        """Automatically wrapped - focus on cleanup."""
        self.logger.info("Shutting down workers...")

        # Cancel all background tasks
        for task in self.background_tasks:
            task.cancel()

        # Wait for them to finish
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Close database connection
        if self.db_connection:
            await self.db_connection.close()
            self.logger.info("Database connection closed")

    # Helper methods
    async def _connect_database(self):
        """Simulate database connection."""
        await asyncio.sleep(0.1)
        return {"status": "connected", "host": "localhost"}

    async def _background_worker(self, name: str):
        """Simulate background work."""
        try:
            while True:
                await asyncio.sleep(1)
                self.logger.debug(f"{name} is working...")
        except asyncio.CancelledError:
            self.logger.info(f"{name} has been cancelled")


# Extended example with custom lifecycle methods
class ExtendedService(BaseService):
    """Example showing how to extend the lifecycle with custom methods."""

    # Add custom lifecycle methods
    _LIFECYCLE_METHODS = {
        **BaseService._LIFECYCLE_METHODS,
        "configure": {
            "from_state": LifecycleState.INITIALIZED,
            "to_state": LifecycleState.INITIALIZED,  # Stay in same state
            "intermediate_state": LifecycleState.INITIALIZED,
        },
    }

    async def configure(self, config: dict[str, Any]) -> None:
        """Custom lifecycle method that's automatically wrapped."""
        self.logger.info(f"Applying configuration: {config}")
        # Configuration logic here
        await asyncio.sleep(0.1)


# Usage demonstration
async def main():
    # Basic service
    service = MyService("auto-wrapped-service")

    print(f"Initial state: {service.state}")

    await service.initialize()  # Automatically wrapped!
    print(f"After initialize: {service.state}")

    await service.start()  # Automatically wrapped!
    print(f"After start: {service.state}")

    await asyncio.sleep(2)  # Let it run

    await service.stop()  # Automatically wrapped!
    print(f"After stop: {service.state}")

    # Extended service example
    extended = ExtendedService("extended-service")
    await extended.initialize()
    await extended.configure({"workers": 5, "timeout": 30})  # Also auto-wrapped!


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
