#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Decorator-Based Approach

Uses decorators to automatically wrap methods with lifecycle behavior.
Good for more complex wrapping logic or when you need multiple types of wrapping.
"""

import asyncio
import logging
from collections.abc import Callable
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


def lifecycle_method(from_state: str, to_state: str, error_state: str = "error"):
    """Decorator that wraps methods with lifecycle state management."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> Any:
            # Pre-execution state check and transition
            if self._state != from_state:
                raise ValueError(f"Cannot {func.__name__} from state {self._state}")

            # Transition to intermediate state
            intermediate_state = f"{func.__name__}ing"
            if hasattr(LifecycleState, intermediate_state.upper()):
                self._state = getattr(LifecycleState, intermediate_state.upper())

            self.logger.info(f"Starting {func.__name__}...")

            try:
                # Execute the actual method
                result = await func(self, *args, **kwargs)

                # Success - transition to target state
                self._state = to_state
                self.logger.info(f"{func.__name__.capitalize()} completed successfully")

                return result

            except Exception as e:
                # Error - transition to error state
                self._state = error_state
                self.logger.error(f"{func.__name__.capitalize()} failed: {e}")
                raise

        return wrapper

    return decorator


class BaseService:
    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._state = LifecycleState.CREATED

    @lifecycle_method(
        from_state=LifecycleState.CREATED, to_state=LifecycleState.INITIALIZED
    )
    async def initialize(self) -> None:
        """Subclasses override this - decoration is automatic."""
        pass

    @lifecycle_method(
        from_state=LifecycleState.INITIALIZED, to_state=LifecycleState.RUNNING
    )
    async def start(self) -> None:
        """Subclasses override this - decoration is automatic."""
        pass

    @lifecycle_method(
        from_state=LifecycleState.RUNNING, to_state=LifecycleState.STOPPED
    )
    async def stop(self) -> None:
        """Subclasses override this - decoration is automatic."""
        pass

    @property
    def state(self) -> str:
        return self._state


class MyService(BaseService):
    """Subclass just implements business logic."""

    def __init__(self, service_id: str):
        super().__init__(service_id)
        self.db_connection = None
        self.workers = []

    async def initialize(self) -> None:
        """The decorator automatically handles state transitions."""
        self.db_connection = await self._connect_database()
        self.logger.info("Database connected")

    async def start(self) -> None:
        """Focus on business logic - lifecycle is handled automatically."""
        for i in range(3):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(task)
        self.logger.info(f"Started {len(self.workers)} workers")

    async def stop(self) -> None:
        """Clean shutdown without state management boilerplate."""
        for task in self.workers:
            task.cancel()

        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)

        if self.db_connection:
            await self.db_connection.close()

    async def _connect_database(self):
        await asyncio.sleep(0.1)
        return {"connected": True}

    async def _worker(self, name: str):
        try:
            while True:
                await asyncio.sleep(1)
                self.logger.debug(f"{name} working...")
        except asyncio.CancelledError:
            self.logger.info(f"{name} stopped")


# Usage
async def main():
    service = MyService("decorated-service")

    await service.initialize()  # Automatically wrapped
    await service.start()  # Automatically wrapped

    await asyncio.sleep(2)

    await service.stop()  # Automatically wrapped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
