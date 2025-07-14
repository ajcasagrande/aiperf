# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import AIPerfUIType, MessageType
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    Message,
    ProfileResultsMessage,
    RecordsProcessingStatsMessage,
    WorkerHealthMessage,
)
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.ui_protocol import AIPerfUIFactory


@AIPerfUIFactory.register(AIPerfUIType.LOGGING)
class SimpleProgressLogger(AIPerfLoggerMixin):
    """Simple logger for progress updates. It will log the progress to the console."""

    def __init__(self, progress_tracker: ProgressTracker, **kwargs):
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker

    async def update_progress(self):
        """Log a progress update based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, phase_stats in current_profile_run.phases.items():
            total_requests = phase_stats.total_requests or 0
            completed_requests = phase_stats.completed

            self.info(
                lambda phase=phase,
                completed=completed_requests,
                total=total_requests: f"Phase {phase} - Requests Completed: {completed} / {total}"
            )

    async def update_stats(self, message: RecordsProcessingStatsMessage):
        """Log a stats update based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, processing_stats in current_profile_run.phases.items():
            processed_records = processing_stats.processed
            total_records = processing_stats.total_records

            self.info(
                lambda phase=phase,
                processed=processed_records,
                total=total_records: f"Phase {phase} - Records Processed: {processed} / {total}"
            )

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        _message_mappings = {
            MessageType.CREDIT_PHASE_PROGRESS: self.update_credit_phase_progress,
            MessageType.CREDIT_PHASE_COMPLETE: self.update_credit_phase_complete,
            MessageType.CREDIT_PHASE_START: self.update_credit_phase_start,
            MessageType.PROCESSING_STATS: self.update_stats,
            MessageType.WORKER_HEALTH: self.update_worker_health,
            MessageType.PROFILE_RESULTS: self.update_results,
        }

        if message.message_type in _message_mappings:
            await _message_mappings[message.message_type](message)
        else:
            self.debug(
                lambda: f"No message mapping found for message: {message.message_type}"
            )

    async def update_worker_health(self, message: WorkerHealthMessage) -> None:
        """Update the worker health."""
        self.debug(lambda: f"Worker health updated: {message}")

    async def update_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Log a credit phase complete update."""
        self.notice(lambda phase=message.phase: f"Credit phase {phase} completed")

    async def update_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Log a credit phase start update."""
        self.notice(lambda phase=message.phase: f"Credit phase {phase} started")

    async def update_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Log a credit phase progress update."""
        self.info(
            lambda phases=message.phase: f"Credit phase {phases} progress updated"
        )

        # This will be handled by update_progress() which is called regularly
        await self.update_progress()

    async def update_results(self, message: ProfileResultsMessage):
        """Log a results update."""
        self.info(lambda: f"Profile results updated: {message.records}")

    def cleanup(self):
        """Clean up all progress bars."""
        pass
