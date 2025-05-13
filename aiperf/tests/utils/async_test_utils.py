"""
Utilities for testing asynchronous code.
"""


async def async_noop():
    """A no-op async function for testing purposes.
    Can be used to replace asyncio.sleep or asyncio.to_thread calls in tests.
    """
    yield
