# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.message_enums import MessageType
from aiperf.common.enums.timing_enums import CreditPhase
from aiperf.common.hooks import background_task, on_message
from aiperf.common.messages.credit_messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
)
from aiperf.common.mixins.message_bus_mixin import MessageBusClientMixin
from aiperf.common.models import CreditPhaseStats


class ProgressMixin(MessageBusClientMixin):
    """Mixin to provide simple progress tracking to a class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase_stats: CreditPhaseStats = CreditPhaseStats(
            type=CreditPhase.PROFILING
        )

    @on_message(MessageType.CREDIT_PHASE_START)
    async def _on_credit_phase_start(self, message: CreditPhaseStartMessage) -> None:
        if self.phase_stats.type != message.phase:
            return
        self.phase_stats.type = message.phase
        self.phase_stats.start_ns = message.start_ns
        self.phase_stats.total_expected_requests = message.total_expected_requests
        self.phase_stats.expected_duration_sec = message.expected_duration_sec
        self.print_progress()

    @on_message(MessageType.CREDIT_PHASE_COMPLETE)
    async def _on_credit_phase_complete(
        self, message: CreditPhaseCompleteMessage
    ) -> None:
        if self.phase_stats.type != message.phase:
            return
        self.phase_stats.completed = message.completed
        self.phase_stats.end_ns = message.end_ns
        self.print_progress()

    @on_message(MessageType.CREDIT_PHASE_PROGRESS)
    async def _on_credit_phase_progress(
        self, message: CreditPhaseProgressMessage
    ) -> None:
        """Handle the credit phase progress message."""
        if self.phase_stats.type != message.phase:
            return
        self.phase_stats.completed = message.completed
        self.phase_stats.sent = message.sent
        # NOTE: We don't need to print the progress here because it will be printed at regular intervals

    @property
    def progress(self) -> float:
        return self.phase_stats.progress_percent or 0.0

    @background_task(interval=5)
    async def _print_progress_task(self) -> None:
        """Print the progress of the credit phase."""
        if self.phase_stats.is_started:
            self.print_progress()

    def print_progress(self) -> None:
        # TODO: Add time based progress printing
        if self.phase_stats.is_request_count_based:
            self.info(
                f"Progress: {self.phase_stats.completed:8,} / {self.phase_stats.total_expected_requests:,} ({self.progress:4.1f}%)"
            )
        else:
            self.info(f"Progress: {self.progress:05.1f}%")
