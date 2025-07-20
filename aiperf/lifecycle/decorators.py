# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Simple, clean decorators for the AIPerf lifecycle system.

These decorators provide a clean, pythonic way to define message handlers,
command handlers, and background tasks without complex configuration.
"""

from collections.abc import Callable


def message_handler(*message_types: str) -> Callable:
    """
    Decorator to mark a method as a message handler.

    The decorated method will be called whenever a message of the specified type(s)
    is received by the service.

    Args:
        *message_types: One or more message type strings to handle

    Example:
        @message_handler("USER_MESSAGE", "SYSTEM_MESSAGE")
        async def handle_messages(self, message):
            self.logger.info(f"Received message: {message}")

        @message_handler("DATA_UPDATE")
        def handle_data_sync(self, message):  # Can be sync or async
            self.process_data(message.data)
    """

    def decorator(func: Callable) -> Callable:
        func._message_types = list(message_types)
        return func

    return decorator


def command_handler(*command_types: str) -> Callable:
    """
    Decorator to mark a method as a command handler.

    The decorated method will be called whenever a command of the specified type(s)
    is received by the service. Commands typically expect a response.

    Args:
        *command_types: One or more command type strings to handle

    Example:
        @command_handler("GET_STATUS")
        async def get_status(self, command):
            return {"status": "running", "uptime": self.get_uptime()}

        @command_handler("RESTART", "RELOAD")
        async def handle_restart_commands(self, command):
            await self.restart()
            return {"result": "success"}
    """

    def decorator(func: Callable) -> Callable:
        func._command_types = list(command_types)
        return func

    return decorator


def background_task(
    interval: float | Callable[[], float] | None = None, run_once: bool = False
) -> Callable:
    """
    Decorator to mark a method as a background task.

    The decorated method will be started automatically when the service starts
    and stopped when the service stops.

    Args:
        interval: Time in seconds between task runs. Can be:
                  - float: Fixed interval (e.g., 5.0 for every 5 seconds)
                  - callable: Function returning interval (for dynamic intervals)
                  - None: Run continuously with no delay
        run_once: If True, task runs only once then exits

    Examples:
        @background_task(interval=10.0)
        async def health_check(self):
            await self.send_heartbeat()

        @background_task(interval=lambda: random.uniform(1, 5))
        async def random_task(self):
            await self.do_random_work()

        @background_task(run_once=True)
        async def startup_task(self):
            await self.initialize_external_systems()

        @background_task()  # Run continuously with no delay
        async def message_processor(self):
            message = await self.queue.get()
            await self.process_message(message)
    """

    def decorator(func: Callable) -> Callable:
        func._is_background_task = True
        func._interval = None if run_once else interval
        func._run_once = run_once
        return func

    return decorator


# Convenience aliases for common patterns
def periodic_task(interval: float | Callable[[], float]) -> Callable:
    """Alias for background_task with an interval."""
    return background_task(interval=interval)


def startup_task() -> Callable:
    """Alias for background_task that runs once at startup."""
    return background_task(run_once=True)


def continuous_task() -> Callable:
    """Alias for background_task that runs continuously."""
    return background_task(interval=None)


# Type-safe decorators for common message types (can be extended)
def on_data_message(func: Callable) -> Callable:
    """Handle DATA_MESSAGE types."""
    return message_handler("DATA_MESSAGE")(func)


def on_status_request(func: Callable) -> Callable:
    """Handle STATUS_REQUEST command types."""
    return command_handler("STATUS_REQUEST")(func)


def on_heartbeat(func: Callable) -> Callable:
    """Handle HEARTBEAT message types."""
    return message_handler("HEARTBEAT")(func)
