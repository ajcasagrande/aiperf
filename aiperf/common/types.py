# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

    from aiperf.common.messages.credit_messages import CreditDropMessage
    from aiperf.common.messages.message import Message
    from aiperf.common.models.record_models import SSEMessage


BaseModelT = TypeVar("BaseModelT", bound="BaseModel")

MessageT = TypeVar("MessageT", bound="Message")
MessageOutputT = TypeVar("MessageOutputT", bound="Message")

RequestInputT = TypeVar("RequestInputT", bound=Any, contravariant=True)
RequestOutputT = TypeVar("RequestOutputT", bound=Any, covariant=True)

InputT = TypeVar("InputT", bound=Any)
OutputT = TypeVar("OutputT", bound=Any)

# Type for coroutines that return None.
CoroutineT = Coroutine[Any, Any, None]

# Type for SSE callbacks.
SSECallbackT = Callable[["SSEMessage"], CoroutineT]

# Type for message handlers.
MessageHandlerT = Callable[[MessageT], CoroutineT]

# Type for credit drop handlers.
CreditDropHandlerT = Callable[["CreditDropMessage"], CoroutineT]

# Type callables that return a string.
StrFuncT = Callable[..., str]
