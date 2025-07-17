# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.mixins import AIPerfLoggerMixin, AIPerfMessageHandlerMixin

# from aiperf.progress.progress_tracker import ProgressTracker


class ProgressTrackerMixin(AIPerfMessageHandlerMixin, AIPerfLoggerMixin):
    """Mixin for the System Controller to track progress."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.progress_tracker: ProgressTracker = ProgressTracker()
