# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Composable AIPerf components with clean single inheritance.

This module provides building blocks that can be used independently or combined
through single inheritance. Each class adds exactly one responsibility.

Available Components:
- BackgroundTasks: Just background task management with decorators
- Messaging: Just messaging with decorators
- Lifecycle: Just lifecycle with on_init/on_start/on_stop
- LifecycleWithTasks: Lifecycle + background tasks
- LifecycleWithMessaging: Lifecycle + messaging
- Service: Everything (lifecycle + tasks + messaging)

Choose exactly what you need!
"""

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from .messaging import Command, Message, MessageBus, get_message_bus
from .tasks import TaskManager, get_task_manager


class BackgroundTasks:
    """
    Just background task management with decorators.

    Use this when you need background tasks but no lifecycle or messaging.
    Tasks are started/stopped manually with start_tasks()/stop_tasks().

    Example:
        class MyWorker(BackgroundTasks):
            def __init__(self):
                super().__init__()

            @background_task(interval=5.0)
            async def do_work(self):
                await self.process_data()

        worker = MyWorker()
        await worker.start_tasks()  # Start background tasks
        # ... do other work ...
        await worker.stop_tasks()   # Stop background tasks
    """

    def __init__(self, task_manager: TaskManager | None = None, **kwargs):
        super().__init__(**kwargs)
        self.task_manager = task_manager or get_task_manager()
        self._tasks: set[asyncio.Task] = set()
        self._task_stop_event = asyncio.Event()

        # Discover background tasks
        self._discover_background_tasks()

    async def start_tasks(self) -> None:
        """Start all background tasks."""
        self._task_stop_event.clear()

        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_is_background_task"):
                interval = getattr(method, "_interval", None)
                run_once = getattr(method, "_run_once", False)

                if run_once:
                    self._tasks.add(
                        self.task_manager.create_task(self._run_once_task(method))
                    )
                else:
                    self._tasks.add(
                        self.task_manager.create_task(
                            self._run_interval_task(method, interval)
                        )
                    )

    async def stop_tasks(self) -> None:
        """Stop all background tasks."""
        self._task_stop_event.set()

        if self._tasks:
            for task in list(self._tasks):
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

    def create_background_task(
        self, coro: Any, name: str | None = None
    ) -> asyncio.Task:
        """Create a background task managed by the task manager."""
        task = self.task_manager.create_task(coro, name)
        self._tasks.add(task)
        return task

    def _discover_background_tasks(self) -> None:
        """Discover background tasks from decorators."""
        # Just discovery, actual starting happens in start_tasks()
        pass

    async def _run_once_task(self, method):
        """Run a task once."""
        try:
            if inspect.iscoroutinefunction(method):
                await method()
            else:
                method()
        except Exception as e:
            if hasattr(self, "logger"):
                self.logger.error(f"Error in one-time task {method.__name__}: {e}")

    async def _run_interval_task(self, method, interval):
        """Run a task with interval."""
        while not self._task_stop_event.is_set():
            try:
                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()

                if interval is None:
                    await asyncio.sleep(0)
                else:
                    sleep_time = interval() if callable(interval) else float(interval)
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if hasattr(self, "logger"):
                    self.logger.error(
                        f"Error in background task {method.__name__}: {e}"
                    )
                await asyncio.sleep(1)


class Messaging:
    """
    Just messaging with decorators.

    Use this when you need message/command handling but no lifecycle or tasks.
    Messaging is started/stopped manually with start_messaging()/stop_messaging().

    Example:
        class MyHandler(Messaging):
            def __init__(self):
                super().__init__(service_id="handler")

            @message_handler("DATA")
            async def handle_data(self, message):
                await self.publish_message("RESULT", processed_data)

            @command_handler("STATUS")
            async def get_status(self, command):
                return {"status": "active"}

        handler = MyHandler()
        await handler.start_messaging()  # Start messaging
        # ... handle messages ...
        await handler.stop_messaging()   # Stop messaging
    """

    def __init__(
        self,
        service_id: str | None = None,
        message_bus: MessageBus | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.service_id = service_id or self.__class__.__name__
        self.message_bus = message_bus or get_message_bus()
        self._message_handlers: dict[str, list[Callable]] = {}
        self._command_handlers: dict[str, list[Callable]] = {}

        # Discover message and command handlers
        self._discover_message_handlers()

    async def start_messaging(self) -> None:
        """Start messaging system."""
        if not self.message_bus._running:
            await self.message_bus.start()

        # Register this component with the message bus
        self.message_bus.register_service(
            self.service_id, self._handle_targeted_message
        )

        # Subscribe to message types this component handles
        for message_type, handlers in self._message_handlers.items():
            if handlers:
                self.message_bus.subscribe(message_type, self._handle_broadcast_message)

    async def stop_messaging(self) -> None:
        """Stop messaging system."""
        self.message_bus.unregister_service(self.service_id)

    async def publish_message(
        self, message_type: str, content: Any = None, target_id: str | None = None
    ) -> None:
        """Publish a message to the message bus."""
        message = Message(
            type=message_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
        )
        await self.message_bus.publish(message)

    async def send_command(
        self,
        command_type: str,
        target_id: str,
        content: Any = None,
        timeout: float = 30.0,
    ) -> Any:
        """Send a command and wait for response."""
        command = Command(
            type=command_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
            timeout=timeout,
        )
        return await self.message_bus.send_command(command, timeout)

    async def reply_to_message(self, original_message: Message, content: Any) -> None:
        """Send a reply to a message."""
        await self.message_bus.send_response(original_message, content)

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
                if hasattr(self, "logger"):
                    self.logger.error(
                        f"Error in message handler {handler.__name__}: {e}"
                    )

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
                if hasattr(self, "logger"):
                    self.logger.error(
                        f"Error in command handler {handler.__name__}: {e}"
                    )
                responses.append({"error": str(e)})

        return responses[0] if len(responses) == 1 else responses

    def _discover_message_handlers(self) -> None:
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

    async def _handle_targeted_message(self, message: Message) -> None:
        """Handle messages targeted specifically to this component."""
        if isinstance(message, Command) and message.expects_response:
            try:
                response = await self.handle_command(message.type, message)
                await self.reply_to_message(message, response)
            except Exception as e:
                if hasattr(self, "logger"):
                    self.logger.error(f"Error handling command {message.type}: {e}")
                await self.reply_to_message(message, {"error": str(e)})
        else:
            await self.handle_message(message.type, message)

    async def _handle_broadcast_message(self, message: Message) -> None:
        """Handle broadcast messages."""
        await self.handle_message(message.type, message)


class Lifecycle:
    """
    Just lifecycle with on_init/on_start/on_stop.

    Use this when you need structured lifecycle but no messaging or tasks.

    Example:
        class MyComponent(Lifecycle):
            def __init__(self):
                super().__init__(component_id="my_component")

            async def on_init(self):
                await super().on_init()
                self.db = await connect_database()

            async def on_start(self):
                await super().on_start()
                self.logger.info("Component ready!")

            async def on_stop(self):
                await super().on_stop()
                await self.db.close()

        component = MyComponent()
        await component.initialize()
        await component.start()
        # ... do work ...
        await component.stop()
    """

    def __init__(
        self,
        component_id: str | None = None,
        logger: logging.Logger | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.component_id = component_id or self.__class__.__name__
        self.logger = logger or logging.getLogger(self.component_id)
        self._lifecycle_state = "created"

    async def on_init(self):
        """Override this method to add initialization logic. Always call super().on_init()"""
        pass

    async def on_start(self):
        """Override this method to add start logic. Always call super().on_start()"""
        pass

    async def on_stop(self):
        """Override this method to add stop and cleanup logic. Always call super().on_stop()"""
        pass

    async def initialize(self) -> None:
        """Initialize the component."""
        if self._lifecycle_state != "created":
            raise ValueError(f"Cannot initialize from state {self._lifecycle_state}")

        self._lifecycle_state = "initializing"

        try:
            await self.on_init()
            self._lifecycle_state = "initialized"
            self.logger.info(f"Component {self.component_id} initialized successfully")
        except Exception as e:
            self._lifecycle_state = "error"
            self.logger.error(
                f"Failed to initialize component {self.component_id}: {e}"
            )
            raise

    async def start(self) -> None:
        """Start the component."""
        if self._lifecycle_state != "initialized":
            raise ValueError(f"Cannot start from state {self._lifecycle_state}")

        self._lifecycle_state = "starting"

        try:
            await self.on_start()
            self._lifecycle_state = "running"
            self.logger.info(f"Component {self.component_id} started successfully")
        except Exception as e:
            self._lifecycle_state = "error"
            self.logger.error(f"Failed to start component {self.component_id}: {e}")
            raise

    async def stop(self) -> None:
        """Stop the component and clean up resources."""
        if self._lifecycle_state in ("stopped", "stopping"):
            return

        self._lifecycle_state = "stopping"

        try:
            await self.on_stop()
            self._lifecycle_state = "stopped"
            self.logger.info(f"Component {self.component_id} stopped successfully")
        except Exception as e:
            self._lifecycle_state = "error"
            self.logger.error(f"Failed to stop component {self.component_id}: {e}")
            raise

    async def run_until_stopped(self, stop_event: asyncio.Event | None = None) -> None:
        """Run the component until stopped."""
        await self.initialize()
        await self.start()

        try:
            if stop_event:
                await stop_event.wait()
            else:
                # Wait forever until manual stop
                while self._lifecycle_state == "running":
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt, stopping component...")
        finally:
            await self.stop()


class LifecycleWithTasks(Lifecycle, BackgroundTasks):
    """
    Lifecycle + background tasks.

    Use this when you need structured lifecycle and background tasks but no messaging.
    Background tasks automatically start with the lifecycle and stop when stopped.

    Example:
        class MyWorkerService(LifecycleWithTasks):
            def __init__(self):
                super().__init__(component_id="worker")

            async def on_init(self):
                await super().on_init()
                self.work_queue = []

            async def on_start(self):
                await super().on_start()  # This starts background tasks automatically
                self.logger.info("Worker service ready!")

            @background_task(interval=5.0)
            async def process_work(self):
                if self.work_queue:
                    item = self.work_queue.pop(0)
                    await self.process_item(item)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_start(self):
        """Start lifecycle and background tasks."""
        await super().on_start()
        await self.start_tasks()

    async def on_stop(self):
        """Stop background tasks and lifecycle."""
        await self.stop_tasks()
        await super().on_stop()


class LifecycleWithMessaging(Lifecycle, Messaging):
    """
    Lifecycle + messaging.

    Use this when you need structured lifecycle and messaging but no background tasks.
    Messaging automatically starts with the lifecycle and stops when stopped.

    Example:
        class MyMessageService(LifecycleWithMessaging):
            def __init__(self):
                super().__init__(component_id="message_service")

            async def on_init(self):
                await super().on_init()
                self.data_store = {}

            async def on_start(self):
                await super().on_start()  # This starts messaging automatically
                self.logger.info("Message service ready!")

            @message_handler("STORE_DATA")
            async def store_data(self, message):
                self.data_store[message.content["key"]] = message.content["value"]

            @command_handler("GET_DATA")
            async def get_data(self, command):
                return self.data_store.get(command.content["key"])
    """

    def __init__(self, **kwargs):
        # Use component_id for both lifecycle and messaging
        if "component_id" in kwargs and "service_id" not in kwargs:
            kwargs["service_id"] = kwargs["component_id"]
        super().__init__(**kwargs)

    async def on_start(self):
        """Start lifecycle and messaging."""
        await super().on_start()
        await self.start_messaging()

    async def on_stop(self):
        """Stop messaging and lifecycle."""
        await self.stop_messaging()
        await super().on_stop()


class Service(LifecycleWithTasks, LifecycleWithMessaging):
    """
    Everything: lifecycle + tasks + messaging.

    This is a full-featured service with all capabilities.
    This is equivalent to the old AIPerf/ManagedLifecycleService.

    Example:
        class MyFullService(Service):
            def __init__(self):
                super().__init__(component_id="full_service")

            async def on_init(self):
                await super().on_init()
                self.db = await connect_database()

            async def on_start(self):
                await super().on_start()  # Starts messaging and tasks
                self.logger.info("Full service ready!")

            @message_handler("PROCESS_DATA")
            async def handle_data(self, message):
                result = await self.process_data(message.content)
                await self.publish_message("DATA_PROCESSED", result)

            @command_handler("GET_STATUS")
            async def get_status(self, command):
                return {"status": "running", "data_count": len(self.data)}

            @background_task(interval=30.0)
            async def cleanup(self):
                await self.cleanup_old_data()
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# Convenience aliases for backward compatibility and clarity
AIPerf = Service
FullService = Service
TaskService = LifecycleWithTasks
MessagingService = LifecycleWithMessaging
