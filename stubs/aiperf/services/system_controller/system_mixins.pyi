#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable
from collections.abc import Coroutine
from typing import Any

class SignalHandlerMixin:
    def __init__(self, *args, **kwargs) -> None: ...
    def setup_signal_handlers(
        self, callback: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None: ...
