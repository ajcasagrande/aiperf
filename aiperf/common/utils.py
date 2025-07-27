# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import inspect
import logging
import os
import traceback
from collections.abc import Callable
from typing import Any

import orjson

from aiperf.common import aiperf_logger
from aiperf.common.exceptions import AIPerfMultiError

logger = logging.getLogger(__name__)


async def call_all_functions_self(
    self_: object, funcs: list[Callable], *args, **kwargs
) -> None:
    """Call all functions in the list with the given name.

    Args:
        obj: The object to call the functions on.
        func_names: The names of the functions to call.
        *args: The arguments to pass to the functions.
        **kwargs: The keyword arguments to pass to the functions.

    Raises:
        AIPerfMultiError: If any of the functions raise an exception.
    """

    exceptions = []
    for func in funcs:
        try:
            if inspect.iscoroutinefunction(func):
                await func(self_, *args, **kwargs)
            else:
                func(self_, *args, **kwargs)
        except Exception as e:
            # TODO: error handling, logging
            traceback.print_exc()
            exceptions.append(e)

    if len(exceptions) > 0:
        raise AIPerfMultiError("Errors calling functions", exceptions)


async def call_all_functions(funcs: list[Callable], *args, **kwargs) -> None:
    """Call all functions in the list with the given name.

    Args:
        obj: The object to call the functions on.
        func_names: The names of the functions to call.
        *args: The arguments to pass to the functions.
        **kwargs: The keyword arguments to pass to the functions.

    Raises:
        AIPerfMultiError: If any of the functions raise an exception.
    """

    exceptions = []
    for func in funcs:
        try:
            if inspect.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        except Exception as e:
            # TODO: error handling, logging
            traceback.print_exc()
            exceptions.append(e)

    if len(exceptions) > 0:
        raise AIPerfMultiError("Errors calling functions", exceptions)


def load_json_str(json_str: str, func: Callable = lambda x: x) -> dict[str, Any]:
    """
    Deserializes JSON encoded string into Python object.

    Args:
      - json_str: string
          JSON encoded string
      - func: callable
          A function that takes deserialized JSON object. This can be used to
          run validation checks on the object. Defaults to identity function.
    """
    try:
        # Note: orjson may not parse JSON the same way as Python's standard json library,
        # notably being stricter on UTF-8 conformance.
        # Refer to https://github.com/ijl/orjson?tab=readme-ov-file#str for details.
        return func(orjson.loads(json_str))
    except orjson.JSONDecodeError:
        snippet = json_str[:200] + ("..." if len(json_str) > 200 else "")
        logger.error("Failed to parse JSON string: '%s'", snippet)
        raise


async def yield_to_event_loop() -> None:
    """Yield to the event loop. This forces the current coroutine to yield and allow
    other coroutines to run, preventing starvation. Use this when you do not want to
    delay your coroutine via sleep, but still want to allow other coroutines to run if
    there is a potential for an infinite loop.
    """
    await asyncio.sleep(0)


def format_duration(seconds: float | None, none_str: str = "--") -> str:
    """Format duration in seconds to human-readable format."""
    if seconds is None:
        return none_str

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60

    if minutes < 60:
        if remaining_seconds < 1:
            return f"{minutes}m"
        return f"{minutes}m {remaining_seconds:.0f}s"

    hours = minutes // 60
    minutes = minutes % 60

    if hours < 24:
        if minutes == 0:
            return f"{hours}h"
        return f"{hours}h {minutes}m"

    days = hours // 24
    hours = hours % 24

    if hours == 0:
        return f"{days}d"
    return f"{days}d {hours}h"


def format_bytes(bytes: int | None, none_str: str = "--") -> str:
    """Format bytes to human-readable format."""
    if bytes is None:
        return none_str
    if bytes < 1000:
        return f"{bytes} B"

    _suffixes = ["KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    for i, suffix in enumerate(_suffixes):
        factor = 1024 ** (i + 1)
        if bytes / factor < 100:
            return f"{bytes / factor:.1f} {suffix}"
        if bytes / factor < 1000:
            return f"{bytes / factor:.0f} {suffix}"

    raise ValueError(f"Bytes value is too large to format: {bytes}")


# This is used to identify the source file of the call_all_functions function
# in the AIPerfLogger class to skip it when determining the caller.
# NOTE: Using similar logic to logging._srcfile
_srcfile = os.path.normcase(call_all_functions.__code__.co_filename)
aiperf_logger._ignored_files.append(_srcfile)
