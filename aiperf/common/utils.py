# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import inspect
import random
import traceback
from collections.abc import Callable

from aiperf.common.exceptions import AIPerfMultiError


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


def sample_bounded_normal(
    mean: float,
    stddev: float,
    lower: float = float("-inf"),
    upper: float = float("inf"),
) -> float:
    """Sample a bounded normal float.

    Args:
        mean: The mean of the normal distribution.
        stddev: The standard deviation of the normal distribution.
        lower: The lower bound of the distribution.
        upper: The upper bound of the distribution.

    Returns:
        A float sampled from the normal distribution, bounded by the lower and upper bounds.
    """
    n = random.gauss(mean, stddev)
    return min(max(lower, n), upper)


def sample_bounded_normal_int(
    mean: float,
    stddev: float,
    lower: float = float("-inf"),
    upper: float = float("inf"),
) -> int:
    """Sample a bounded normal integer.

    Args:
        mean: The mean of the normal distribution.
        stddev: The standard deviation of the normal distribution.
        lower: The lower bound of the distribution.
        upper: The upper bound of the distribution.

    Returns:
        An integer sampled from the normal distribution, bounded by the lower and upper bounds.
    """
    return round(sample_bounded_normal(mean, stddev, lower, upper))
