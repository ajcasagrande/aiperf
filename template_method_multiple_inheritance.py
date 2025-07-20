#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Template Method Pattern with Multiple Inheritance

This example shows why you still need super() calls in hook methods
when using multiple inheritance, even with the template method pattern.
"""

import asyncio
import logging


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
    """Base service with template method pattern."""

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._state = LifecycleState.CREATED

    # Template methods - these handle the framework behavior
    async def initialize(self) -> None:
        """Template method - handles state and calls hook."""
        if self._state != LifecycleState.CREATED:
            raise ValueError(f"Cannot initialize from state {self._state}")

        self._state = LifecycleState.INITIALIZING
        self.logger.info("Starting initialization...")

        try:
            await self._initialize_impl()  # Call the hook method
            self._state = LifecycleState.INITIALIZED
            self.logger.info("Initialization completed")
        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Initialization failed: {e}")
            raise

    # Hook methods - subclasses and mixins override these
    async def _initialize_impl(self) -> None:
        """Hook method for initialization logic."""
        pass  # Base implementation does nothing

    @property
    def state(self) -> str:
        """Current lifecycle state."""
        return self._state


class DatabaseMixin:
    """Mixin that adds database functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Important for MRO!
        self.db_connection = None

    async def _initialize_impl(self) -> None:
        """Database initialization - MUST call super() for MRO!"""
        await super()._initialize_impl()  # Critical for multiple inheritance!

        self.logger.info("Connecting to database...")
        self.db_connection = await self._connect_database()
        self.logger.info("Database connected")

    async def _connect_database(self):
        await asyncio.sleep(0.1)
        return {"status": "connected", "host": "localhost"}


class CacheMixin:
    """Mixin that adds caching functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Important for MRO!
        self.cache = None

    async def _initialize_impl(self) -> None:
        """Cache initialization - MUST call super() for MRO!"""
        await super()._initialize_impl()  # Critical for multiple inheritance!

        self.logger.info("Initializing cache...")
        self.cache = await self._setup_cache()
        self.logger.info("Cache initialized")

    async def _setup_cache(self):
        await asyncio.sleep(0.05)
        return {"status": "ready", "size": 1000}


class MetricsMixin:
    """Mixin that adds metrics functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Important for MRO!
        self.metrics_client = None

    async def _initialize_impl(self) -> None:
        """Metrics initialization - MUST call super() for MRO!"""
        await super()._initialize_impl()  # Critical for multiple inheritance!

        self.logger.info("Initializing metrics...")
        self.metrics_client = await self._setup_metrics()
        self.logger.info("Metrics initialized")

    async def _setup_metrics(self):
        await asyncio.sleep(0.02)
        return {"status": "connected", "endpoint": "metrics.example.com"}


# Multiple inheritance example - ORDER MATTERS!
class MyComplexService(DatabaseMixin, CacheMixin, MetricsMixin, BaseService):
    """
    Service using multiple mixins.

    MRO (Method Resolution Order) will be:
    MyComplexService -> DatabaseMixin -> CacheMixin -> MetricsMixin -> BaseService -> object

    Note: Mixins come BEFORE BaseService so their _initialize_impl methods are called first
    """

    def __init__(self, service_id: str):
        super().__init__(service_id)  # Calls through the entire MRO chain
        self.workers = []

    async def _initialize_impl(self) -> None:
        """
        Service-specific initialization.
        MUST call super() to ensure all mixins get initialized!
        """
        await super()._initialize_impl()  # This calls through ALL the mixins!

        # Now do service-specific initialization
        self.logger.info("Setting up service-specific resources...")
        await self._setup_workers()
        self.logger.info("Service-specific initialization complete")

    async def _setup_workers(self):
        """Service-specific setup."""
        await asyncio.sleep(0.1)
        self.workers = [f"worker-{i}" for i in range(3)]


# Example showing what happens WITHOUT super() calls (BROKEN!)
class BrokenService(DatabaseMixin, CacheMixin, BaseService):
    """Example of what goes wrong without super() calls."""

    async def _initialize_impl(self) -> None:
        """BROKEN: Doesn't call super() - mixins won't be initialized!"""
        # await super()._initialize_impl()  # ← Missing this!

        self.logger.info("Only service logic runs...")
        # Database and Cache mixins are never initialized!


# Demonstration
async def demo_correct_multiple_inheritance():
    """Show correct multiple inheritance with template method."""
    print("=== CORRECT Multiple Inheritance ===")

    service = MyComplexService("complex-service")

    print(f"MRO: {[cls.__name__ for cls in MyComplexService.__mro__]}")
    print(f"Initial state: {service.state}")

    # This will initialize everything in the correct order
    await service.initialize()

    print(f"Final state: {service.state}")
    print(f"Database: {service.db_connection}")
    print(f"Cache: {service.cache}")
    print(f"Metrics: {service.metrics_client}")
    print(f"Workers: {service.workers}")


async def demo_broken_multiple_inheritance():
    """Show what happens when super() calls are missing."""
    print("\n=== BROKEN Multiple Inheritance ===")

    service = BrokenService("broken-service")
    await service.initialize()

    print(f"Database: {getattr(service, 'db_connection', 'NOT INITIALIZED')}")
    print(f"Cache: {getattr(service, 'cache', 'NOT INITIALIZED')}")
    print("↑ Mixins were never initialized because super() wasn't called!")


# Best practice example
class BestPracticeService(DatabaseMixin, CacheMixin, BaseService):
    """
    Best practice: Always call super() in hook methods, even if you think
    you don't need it. This makes your code future-proof for multiple inheritance.
    """

    async def _initialize_impl(self) -> None:
        # ALWAYS call super() first - even in simple cases
        await super()._initialize_impl()

        # Then do your specific initialization
        self.logger.info("Service-specific initialization")
        self.business_logic_initialized = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo_correct_multiple_inheritance())
    asyncio.run(demo_broken_multiple_inheritance())
