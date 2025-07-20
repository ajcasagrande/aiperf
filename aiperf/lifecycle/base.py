# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Core lifecycle management for AIPerf services.

This module provides the fundamental LifecycleService class that offers
clean, inheritance-based lifecycle management without complex mixins or decorators.
"""

import asyncio
import inspect
import logging
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
    A simple, powerful base class for service lifecycle management.

    This class provides clean lifecycle management through simple method overrides.
    No complex mixins, decorators, or configuration required - just inherit and implement
    the lifecycle methods you need.

    Lifecycle Methods (override as needed):
        - on_init(): Called during initialization
        - on_start(): Called when service starts
        - on_stop(): Called when service stops
        - on_cleanup(): Called during final cleanup
        - on_state_change(old_state, new_state): Called on state transitions

    Message Handling:
        Use @message_handler and @command_handler decorators on methods.

    Background Tasks:
        Use @background_task decorator on methods.

    Example:
        class MyService(LifecycleService):
            def __init__(self, name: str):
                super().__init__(service_id=name)
                self.data = []

            async def on_init(self):
                self.logger.info("Setting up database connection...")
                self.db = await connect_database()

            async def on_start(self):
                self.logger.info("Service is now running!")

            @message_handler("DATA_MESSAGE")
            async def handle_data(self, message):
                self.data.append(message.content)

            @background_task(interval=10.0)
            async def periodic_cleanup(self):
                await self.cleanup_old_data()
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
        self._message_handlers: dict[str, list[callable]] = {}
        self._command_handlers: dict[str, list[callable]] = {}

        # Auto-discover decorated methods
        self._discover_handlers()

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

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._state != LifecycleState.CREATED:
            raise ValueError(f"Cannot initialize from state {self._state}")

        await self._change_state(LifecycleState.INITIALIZING)

        try:
            # Call user's initialization logic
            if hasattr(self, "on_init") and inspect.iscoroutinefunction(self.on_init):
                await self.on_init()
            elif hasattr(self, "on_init"):
                self.on_init()

            await self._change_state(LifecycleState.INITIALIZED)
            self.logger.info(f"Service {self.service_id} initialized successfully")

        except Exception as e:
            await self._change_state(LifecycleState.ERROR)
            self.logger.error(f"Failed to initialize service {self.service_id}: {e}")
            raise

    async def start(self) -> None:
        """Start the service."""
        if self._state != LifecycleState.INITIALIZED:
            raise ValueError(f"Cannot start from state {self._state}")

        await self._change_state(LifecycleState.STARTING)

        try:
            # Start background tasks
            await self._start_background_tasks()

            # Call user's start logic
            if hasattr(self, "on_start") and inspect.iscoroutinefunction(self.on_start):
                await self.on_start()
            elif hasattr(self, "on_start"):
                self.on_start()

            await self._change_state(LifecycleState.RUNNING)
            self.logger.info(f"Service {self.service_id} started successfully")

        except Exception as e:
            await self._change_state(LifecycleState.ERROR)
            self.logger.error(f"Failed to start service {self.service_id}: {e}")
            raise

    async def stop(self) -> None:
        """Stop the service."""
        if self._state in (LifecycleState.STOPPED, LifecycleState.STOPPING):
            return

        await self._change_state(LifecycleState.STOPPING)

        try:
            # Signal stop to background tasks
            self._stop_event.set()

            # Call user's stop logic
            if hasattr(self, "on_stop") and inspect.iscoroutinefunction(self.on_stop):
                await self.on_stop()
            elif hasattr(self, "on_stop"):
                self.on_stop()

            # Stop background tasks
            await self._stop_background_tasks()

            # Call user's cleanup logic
            if hasattr(self, "on_cleanup") and inspect.iscoroutinefunction(
                self.on_cleanup
            ):
                await self.on_cleanup()
            elif hasattr(self, "on_cleanup"):
                self.on_cleanup()

            await self._change_state(LifecycleState.STOPPED)
            self.logger.info(f"Service {self.service_id} stopped successfully")

        except Exception as e:
            await self._change_state(LifecycleState.ERROR)
            self.logger.error(f"Failed to stop service {self.service_id}: {e}")
            raise

    async def run_until_stopped(self) -> None:
        """Run the service until stop() is called."""
        await self.initialize()
        await self.start()

        try:
            # Wait until stopped
            await self._stop_event.wait()
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt, stopping service...")
        finally:
            await self.stop()

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

    def create_task(self, coro) -> asyncio.Task:
        """Create and track a background task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _change_state(self, new_state: LifecycleState) -> None:
        """Change the service state and notify."""
        old_state = self._state
        self._state = new_state

        self.logger.debug(f"State changed from {old_state.value} to {new_state.value}")

        # Call user's state change handler if it exists
        if hasattr(self, "on_state_change"):
            try:
                if inspect.iscoroutinefunction(self.on_state_change):
                    await self.on_state_change(old_state, new_state)
                else:
                    self.on_state_change(old_state, new_state)
            except Exception as e:
                self.logger.error(f"Error in state change handler: {e}")

    def _discover_handlers(self) -> None:
        """Automatically discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Check for message handler decorator
            if hasattr(method, "_message_types"):
                for msg_type in method._message_types:
                    self._message_handlers.setdefault(msg_type, []).append(method)

            # Check for command handler decorator
            if hasattr(method, "_command_types"):
                for cmd_type in method._command_types:
                    self._command_handlers.setdefault(cmd_type, []).append(method)

    async def _start_background_tasks(self) -> None:
        """Start all background tasks."""
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_is_background_task"):
                interval = getattr(method, "_interval", None)
                task_coro = self._create_background_task_wrapper(method, interval)
                self.create_task(task_coro)
                self.logger.debug(f"Started background task: {name}")

    async def _create_background_task_wrapper(self, method, interval):
        """Wrapper for background tasks with interval support."""
        while not self._stop_event.is_set():
            try:
                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()

                if interval is None:
                    break  # Run once

                if callable(interval):
                    sleep_time = interval()
                else:
                    sleep_time = float(interval)

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
