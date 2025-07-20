# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Core lifecycle management for AIPerf services.

This module provides a simple, inheritance-based lifecycle service that uses
standard Python inheritance patterns for lifecycle methods and decorators only
for dynamic handlers (messages, commands, background tasks).
"""

import asyncio
import inspect
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any


class LifecycleState(Enum):
    """Service lifecycle states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class LifecycleService:
    """
    Simple lifecycle service with inheritance-based lifecycle management.

    This class provides clean lifecycle management through simple method inheritance.
    Just override the lifecycle methods you need and call super() to chain properly.

    Lifecycle Methods (override and call super()):
        - async def initialize(self): Initialize resources
        - async def start(self): Start the service
        - async def stop(self): Stop the service and clean up resources

    Dynamic Handlers (use decorators):
        - @message_handler("TYPE") for message handling
        - @command_handler("TYPE") for command handling
        - @background_task(interval=5.0) for background tasks

    Example:
        class MyService(LifecycleService):
            def __init__(self):
                super().__init__(service_id="my_service")

            async def initialize(self):
                await super().initialize()  # Always call super()
                self.db = await connect_database()

            async def start(self):
                await super().start()  # Always call super()
                self.logger.info("Service ready!")

            async def stop(self):
                await super().stop()  # Always call super()
                await self.db.close()  # Stop AND cleanup in one step

            @message_handler("DATA")
            async def handle_data(self, message):
                await self.process(message.content)

            @background_task(interval=10.0)
            async def health_check(self):
                await self.send_heartbeat()
    """

    def __init__(
        self,
        service_id: str | None = None,
        logger: logging.Logger | None = None,
        **kwargs,
    ):
        self.service_id = service_id or self.__class__.__name__
        self.logger = logger or logging.getLogger(self.service_id)
        self._state = LifecycleState.CREATED
        self._stop_event = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        self._message_handlers: dict[str, list[Callable]] = {}
        self._command_handlers: dict[str, list[Callable]] = {}

        # Discover only decorated handlers (not lifecycle methods)
        self._discover_decorated_handlers()

    @property
    def state(self) -> LifecycleState:
        """Current lifecycle state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """True if service is in running state."""
        return self._state == LifecycleState.RUNNING

    @property
    def is_stopped(self) -> bool:
        """True if service is stopped."""
        return self._state == LifecycleState.STOPPED

    # =================================================================
    # Simple Lifecycle Methods - Override and Call super()
    # =================================================================

    async def initialize(self):
        """Override this method to add initialization logic. Always call super().initialize()"""
        pass

    async def start(self):
        """Override this method to add start logic. Always call super().start()"""
        # Start background tasks
        await self._start_background_tasks()

    async def stop(self):
        """Override this method to add stop and cleanup logic. Always call super().stop()"""
        # Stop background tasks
        await self._stop_background_tasks()

    # =================================================================
    # Main Lifecycle Control Methods
    # =================================================================

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._state != LifecycleState.CREATED:
            raise ValueError(f"Cannot initialize from state {self._state}")

        self._state = LifecycleState.INITIALIZING

        try:
            await self.initialize()
            self._state = LifecycleState.INITIALIZED
            self.logger.info(f"Service {self.service_id} initialized successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Failed to initialize service {self.service_id}: {e}")
            raise

    async def start(self) -> None:
        """Start the service."""
        if self._state != LifecycleState.INITIALIZED:
            raise ValueError(f"Cannot start from state {self._state}")

        self._state = LifecycleState.STARTING

        try:
            await self.start()
            self._state = LifecycleState.RUNNING
            self.logger.info(f"Service {self.service_id} started successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Failed to start service {self.service_id}: {e}")
            raise

    async def stop(self) -> None:
        """Stop the service and clean up resources."""
        if self._state in (LifecycleState.STOPPED, LifecycleState.STOPPING):
            return

        self._state = LifecycleState.STOPPING

        try:
            self._stop_event.set()
            await self.stop()  # Does both stop and cleanup in one step
            self._state = LifecycleState.STOPPED
            self.logger.info(f"Service {self.service_id} stopped successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Failed to stop service {self.service_id}: {e}")
            raise

    async def run_until_stopped(self) -> None:
        """Run the service until stop() is called."""
        await self.initialize()
        await self.start()

        try:
            await self._stop_event.wait()
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt, stopping service...")
        finally:
            await self.stop()

    # =================================================================
    # Message and Command Handling
    # =================================================================

    async def handle_message(self, message_type: str, message: Any) -> None:
        """Handle an incoming message."""
        handlers = self._message_handlers.get(message_type, [])
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler {handler.__name__}: {e}")

    async def handle_command(self, command_type: str, command: Any) -> Any:
        """Handle an incoming command and return response."""
        handlers = self._command_handlers.get(command_type, [])
        responses = []

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(command)
                else:
                    result = handler(command)
                responses.append(result)
            except Exception as e:
                self.logger.error(f"Error in command handler {handler.__name__}: {e}")
                responses.append({"error": str(e)})

        return responses[0] if len(responses) == 1 else responses

    # =================================================================
    # Task Management
    # =================================================================

    def create_task(self, coro) -> asyncio.Task:
        """Create and track a background task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    # =================================================================
    # Internal Implementation
    # =================================================================

    def _discover_decorated_handlers(self) -> None:
        """Discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Message handlers
            if hasattr(method, "_message_types"):
                for msg_type in method._message_types:
                    self._message_handlers.setdefault(msg_type, []).append(method)

            # Command handlers
            if hasattr(method, "_command_types"):
                for cmd_type in method._command_types:
                    self._command_handlers.setdefault(cmd_type, []).append(method)

    async def _start_background_tasks(self) -> None:
        """Start all background tasks."""
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_is_background_task"):
                interval = getattr(method, "_interval", None)
                run_once = getattr(method, "_run_once", False)

                if run_once:
                    # Run once then exit
                    self.create_task(self._run_once_task(method))
                else:
                    # Run with interval
                    self.create_task(self._run_interval_task(method, interval))

                self.logger.debug(f"Started background task: {name}")

    async def _run_once_task(self, method):
        """Run a task once."""
        try:
            if inspect.iscoroutinefunction(method):
                await method()
            else:
                method()
        except Exception as e:
            self.logger.error(f"Error in one-time task {method.__name__}: {e}")

    async def _run_interval_task(self, method, interval):
        """Run a task with interval."""
        while not self._stop_event.is_set():
            try:
                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()

                if interval is None:
                    # Run continuously with no delay
                    await asyncio.sleep(0)
                else:
                    sleep_time = interval() if callable(interval) else float(interval)
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in background task {method.__name__}: {e}")
                await asyncio.sleep(1)  # Brief pause before retry

    async def _stop_background_tasks(self) -> None:
        """Stop all background tasks."""
        if not self._tasks:
            return

        # Cancel all tasks
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

        # Wait for cancellation to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self.logger.debug(f"Stopped {len(self._tasks)} background tasks")
        self._tasks.clear()
