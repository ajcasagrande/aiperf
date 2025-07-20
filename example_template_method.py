#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Template Method Pattern - Recommended Approach

The base class controls the workflow and state management,
while subclasses implement specific business logic via hook methods.
"""

import asyncio
import logging
from abc import ABC


class LifecycleState:
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class BaseService(ABC):
    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._state = LifecycleState.CREATED

    # Template methods - control the workflow
    async def initialize(self) -> None:
        """Template method that handles state and calls hook."""
        if self._state != LifecycleState.CREATED:
            raise ValueError(f"Cannot initialize from state {self._state}")

        self._state = LifecycleState.INITIALIZING
        self.logger.info("Starting initialization...")

        try:
            # Call the hook method that subclasses implement
            await self._initialize_impl()

            self._state = LifecycleState.INITIALIZED
            self.logger.info("Initialization completed successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Initialization failed: {e}")
            raise

    async def start(self) -> None:
        """Template method that handles state and calls hook."""
        if self._state != LifecycleState.INITIALIZED:
            raise ValueError(f"Cannot start from state {self._state}")

        self._state = LifecycleState.STARTING
        self.logger.info("Starting service...")

        try:
            await self._start_impl()

            self._state = LifecycleState.RUNNING
            self.logger.info("Service started successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Start failed: {e}")
            raise

    async def stop(self) -> None:
        """Template method that handles state and calls hook."""
        if self._state in (LifecycleState.STOPPED, LifecycleState.STOPPING):
            return

        self._state = LifecycleState.STOPPING
        self.logger.info("Stopping service...")

        try:
            await self._stop_impl()

            self._state = LifecycleState.STOPPED
            self.logger.info("Service stopped successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Stop failed: {e}")
            raise

    # Hook methods - subclasses implement these
    async def _initialize_impl(self) -> None:
        """Override this to add initialization logic. No need to call super()!"""
        pass

    async def _start_impl(self) -> None:
        """Override this to add start logic. No need to call super()!"""
        pass

    async def _stop_impl(self) -> None:
        """Override this to add stop logic. No need to call super()!"""
        pass

    @property
    def state(self) -> str:
        return self._state


class MyService(BaseService):
    """Example subclass - clean and simple!"""

    def __init__(self, service_id: str):
        super().__init__(service_id)
        self.db_connection = None
        self.worker_tasks = []

    async def _initialize_impl(self) -> None:
        """Just implement business logic - framework handles the rest!"""
        self.db_connection = await self._connect_database()
        self.logger.info("Database connected")

    async def _start_impl(self) -> None:
        """Start workers without worrying about state management."""
        for i in range(3):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(task)
        self.logger.info(f"Started {len(self.worker_tasks)} workers")

    async def _stop_impl(self) -> None:
        """Clean shutdown logic only."""
        # Cancel workers
        for task in self.worker_tasks:
            task.cancel()

        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        # Close database
        if self.db_connection:
            await self.db_connection.close()

        self.logger.info("Cleanup completed")

    async def _connect_database(self):
        """Simulate database connection."""
        await asyncio.sleep(0.1)
        return {"connected": True}

    async def _worker(self, name: str):
        """Example worker task."""
        try:
            while True:
                await asyncio.sleep(1)
                self.logger.debug(f"{name} working...")
        except asyncio.CancelledError:
            self.logger.info(f"{name} stopped")


# Usage - Clean and error-free!
async def main():
    service = MyService("example-service")

    await service.initialize()  # State management is automatic
    await service.start()  # No super() calls needed

    await asyncio.sleep(2)  # Let it run

    await service.stop()  # Cleanup is guaranteed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
