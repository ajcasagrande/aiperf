# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from tqdm import tqdm

from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.enums.ui import AIPerfUIType
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    Message,
    ProfileResultsMessage,
    RecordsProcessingStatsMessage,
    WorkerHealthMessage,
)
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.ui_protocol import AIPerfUIFactory


@AIPerfUIFactory.register(AIPerfUIType.TQDM)
class TqdmProgressUI(AIPerfLifecycleMixin):
    """Tqdm progress UI."""

    def __init__(self, progress_tracker: ProgressTracker, **kwargs):
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker
        self.tqdm_requests: dict[CreditPhase, tqdm] = {}
        self.tqdm_records: dict[CreditPhase, tqdm] = {}

    async def update_progress(self):
        """Log a progress update based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, phase_stats in current_profile_run.phases.items():
            total_requests = phase_stats.total_requests or 0
            completed_requests = phase_stats.completed

            # Only create tqdm if we have a valid total > 0
            if phase not in self.tqdm_requests and total_requests > 0:
                self.tqdm_requests[phase] = tqdm(
                    total=total_requests,
                    desc=f"Requests ({phase.capitalize()})",
                    colour="green" if phase == CreditPhase.PROFILING else "yellow",
                )

            if phase in self.tqdm_requests:
                self.tqdm_requests[phase].n = completed_requests
                self.tqdm_requests[phase].refresh()

            # Close tqdm when completed
            if (
                total_requests > 0
                and completed_requests >= total_requests
                and phase in self.tqdm_requests
            ):
                self.tqdm_requests[phase].close()
                del self.tqdm_requests[phase]

    async def update_stats(self, message: RecordsProcessingStatsMessage):
        """Log a stats update based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, processing_stats in current_profile_run.phases.items():
            processed_records = processing_stats.processed
            total_records = processing_stats.total_records

            # Only create tqdm if we have a valid total > 0
            if phase not in self.tqdm_records and total_records > 0:
                self.tqdm_records[phase] = tqdm(
                    total=total_records,
                    desc=f" Records ({phase.capitalize()})",
                    colour="blue",
                )

            if phase in self.tqdm_records:
                self.tqdm_records[phase].n = processed_records
                self.tqdm_records[phase].refresh()

            # Close tqdm when completed
            if (
                total_records > 0
                and processed_records >= total_records
                and phase in self.tqdm_records
            ):
                self.debug(
                    lambda phase=phase,
                    processed=processed_records,
                    total=total_records: f"Phase {phase} - Closing TQDM. Records Processed: {processed} / {total}",
                )
                self.tqdm_records[phase].close()
                del self.tqdm_records[phase]

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
            self.logger.debug(
                "No message mapping found for message: %s", message.message_type
            )

    async def update_worker_health(self, message: WorkerHealthMessage) -> None:
        """Update the worker health."""
        self.logger.debug("Worker health updated: %s", message)

    async def update_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Log a credit phase complete update."""
        self.logger.debug("Credit phase %s completed", message.phase)

        if message.phase in self.tqdm_requests:
            self.tqdm_requests[message.phase].close()
            del self.tqdm_requests[message.phase]

        if message.phase in self.tqdm_records:
            self.tqdm_records[message.phase].close()
            del self.tqdm_records[message.phase]

    async def update_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Log a credit phase start update."""
        self.logger.debug("Credit phase %s started", message.phase)
        phase = message.phase

        # Close any existing tqdm for this phase
        if phase in self.tqdm_requests:
            self.tqdm_requests[phase].close()
            del self.tqdm_requests[phase]

        if phase in self.tqdm_records:
            self.tqdm_records[phase].close()
            del self.tqdm_records[phase]

    async def update_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Log a credit phase progress update."""
        await self.update_progress()

    async def update_results(self, message: ProfileResultsMessage):
        """Log a results update."""
        pass

    async def cleanup(self):
        """Clean up all progress bars."""

        for _, tqdm_bar in list(self.tqdm_requests.items()):
            tqdm_bar.close()
        self.tqdm_requests.clear()

        for _, tqdm_bar in list(self.tqdm_records.items()):
            tqdm_bar.close()
        self.tqdm_records.clear()
