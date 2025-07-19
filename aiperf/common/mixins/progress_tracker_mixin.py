# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin
from aiperf.common.mixins.aiperf_message_mixins import AIPerfMessageHandlerMixin


class ProgressTrackerMixin(AIPerfMessageHandlerMixin, AIPerfLoggerMixin):
    """Mixin for the System Controller to track progress."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.progress_tracker: ProgressTracker = ProgressTracker()
