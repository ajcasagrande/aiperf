# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import signal
from collections.abc import Callable, Coroutine
from typing import Any

from aiperf.common.mixins import AsyncTaskManagerMixin


class SignalHandlerMixin(AsyncTaskManagerMixin):
    """Mixin for services that need to handle system signals."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def setup_signal_handlers(
        self, callback: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None:
        """This method will set up signal handlers for the SIGTERM and SIGINT signals
        in order to trigger a graceful shutdown of the service.

        Args:
            callback: The callback to call when a signal is received
        """
        loop = asyncio.get_running_loop()

        def signal_handler(sig: int) -> None:
            self.logger.info("Received signal %s", sig)
            self.execute_async(callback(sig))

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
