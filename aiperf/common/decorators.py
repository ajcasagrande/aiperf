# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Decorators for AIPerf components. Note that these are not the same as hooks.
Hooks are used to specify that a function should be called at a specific time,
while decorators are used to specify that a class or function should be treated a specific way.

see also: :mod:`aiperf.common.hooks` for hook decorators.
"""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING
from warnings import warn

from aiperf.cli_utils import exit_on_error as _exit_on_error
from aiperf.common.types import ClassProtocolT, ProtocolT


class DecoratorAttrs:
    """Constant attribute names for decorators.

    When you decorate a class with a decorator, the decorator type and parameters are
    set as attributes on the class.
    """

    IMPLEMENTS_PROTOCOL = "__implements_protocol__"


def implements_protocol(protocol: type[ProtocolT]) -> Callable:
    """Decorator to specify that the class implements the given protocol.

    Example:
    ```python
    @implements_protocol(ServiceProtocol)
    class BaseService:
        pass
    ```

    The above is the equivalent to setting:
    ```python
    BaseService.__implements_protocol__ = ServiceProtocol
    ```
    """

    def decorator(cls: type[ClassProtocolT]) -> type[ClassProtocolT]:
        if TYPE_CHECKING:
            if not hasattr(protocol, "_is_runtime_protocol"):
                warn(
                    f"Protocol {protocol.__name__} is not a runtime protocol. "
                    "Please use the @runtime_checkable decorator to mark it as a runtime protocol.",
                    category=UserWarning,
                    stacklevel=2,
                )
                raise TypeError(
                    f"Protocol {protocol.__name__} is not a runtime protocol. "
                    "Please use the @runtime_checkable decorator to mark it as a runtime protocol."
                )
            if not issubclass(cls, protocol):
                warn(
                    f"Class {cls.__name__} does not implement the {protocol.__name__} protocol.",
                    category=UserWarning,
                    stacklevel=2,
                )
                raise TypeError(
                    f"Class {cls.__name__} does not implement the {protocol.__name__} protocol."
                )
        setattr(cls, DecoratorAttrs.IMPLEMENTS_PROTOCOL, protocol)
        return cls

    return decorator


def exit_on_error(*exceptions: type[BaseException], title: str = "Error") -> Callable:
    """Decorator to exit the program if an error occurs.

    Args:
        title: The title of the error.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with _exit_on_error(*exceptions, title=title):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
