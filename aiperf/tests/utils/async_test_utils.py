"""
Utilities for testing asynchronous code.
"""

import asyncio
import contextlib
import functools
from typing import Any, Awaitable, Callable, Generator, TypeVar, Union

T = TypeVar("T")


class AsyncTestUtils:
    """Utilities for testing asynchronous code."""

    @staticmethod
    @contextlib.contextmanager
    def timeout_context(seconds: float) -> Generator[None, None, None]:
        """
        Context manager for timing out async operations.

        Args:
            seconds: Number of seconds before timeout

        Yields:
            None

        Raises:
            asyncio.TimeoutError: If the operation times out
        """
        loop = asyncio.get_event_loop()
        task = asyncio.current_task()
        handle = loop.call_later(seconds, task.cancel)
        try:
            yield
        except asyncio.CancelledError:
            raise asyncio.TimeoutError(f"Operation timed out after {seconds} seconds")
        finally:
            handle.cancel()

    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], Union[bool, Awaitable[bool]]],
        timeout: float = 5.0,
        check_interval: float = 0.1,
        message: str = "Condition not met within timeout",
    ) -> None:
        """
        Wait for a condition to be met, with timeout.

        Args:
            condition: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            check_interval: How often to check the condition
            message: Error message if timeout occurs

        Raises:
            asyncio.TimeoutError: If the condition is not met within the timeout
        """

        async def _check_condition() -> bool:
            result = condition()
            if asyncio.iscoroutine(result):
                return await result
            return result

        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if await _check_condition():
                return
            await asyncio.sleep(check_interval)

        raise asyncio.TimeoutError(message)

    @staticmethod
    async def wait_for_messages(
        mock_communication,
        topic: str,
        count: int = 1,
        timeout: float = 5.0,
        check_interval: float = 0.1,
    ) -> None:
        """
        Wait for a specific number of messages to be published to a topic.

        Args:
            mock_communication: The mock communication object
            topic: The topic to check
            count: Minimum number of messages to wait for
            timeout: Maximum time to wait in seconds
            check_interval: How often to check for messages

        Raises:
            asyncio.TimeoutError: If not enough messages are received within the timeout
        """

        def _check_message_count() -> bool:
            if topic not in mock_communication.published_messages:
                return False
            return len(mock_communication.published_messages[topic]) >= count

        await AsyncTestUtils.wait_for_condition(
            _check_message_count,
            timeout=timeout,
            check_interval=check_interval,
            message=f"Did not receive {count} messages on topic {topic} within {timeout} seconds",
        )


def async_test(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """
    Decorator for running async test functions with proper event loop handling.

    Args:
        func: The async test function to wrap

    Returns:
        A synchronous function that runs the async function in an event loop
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(func(*args, **kwargs))
        finally:
            loop.close()

    return wrapper


async def async_noop():
    """A no-op async function for testing purposes.
    Can be used to replace sleep or other async calls in tests.
    """
    yield
