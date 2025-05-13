"""
Utilities for testing asynchronous code.
"""


async def async_noop():
    """A no-op async function for testing purposes.
    Can be used to replace sleep or other async calls in tests.
    """
    yield
