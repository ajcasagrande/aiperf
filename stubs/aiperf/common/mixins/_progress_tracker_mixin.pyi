#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.mixins._aiperf_logger import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.mixins._aiperf_message_handler import (
    AIPerfMessageHandlerMixin as AIPerfMessageHandlerMixin,
)

class ProgressTrackerMixin(AIPerfMessageHandlerMixin, AIPerfLoggerMixin):
    def __init__(self, *args, **kwargs) -> None: ...
