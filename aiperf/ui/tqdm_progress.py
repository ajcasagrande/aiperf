# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from tqdm import tqdm

from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.enums.ui_enums import AIPerfUIType
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


@AIPerfUIFactory.register(AIPerfUIType.BASIC)
class TqdmProgressUI(AIPerfLifecycleMixin):
    """Tqdm progress UI."""

    def __init__(self, progress_tracker: ProgressTracker, **kwargs):
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker
        self.tqdm_requests: dict[CreditPhase, tqdm] = {}
        self.tqdm_records: dict[CreditPhase, tqdm] = {}

    async def update_progress(self):
        """Update progress bars based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, phase_stats in current_profile_run.phase_infos.items():
            total_requests = phase_stats.total_expected_requests or 0
            completed_requests = phase_stats.completed

            # Only create tqdm if we have a valid total > 0 (right now just supporting count-based progress)
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
                # TODO: There seems to be an issue where the tqdm bar keeps showing even after it is closed.
                self.tqdm_requests[phase].close()
                del self.tqdm_requests[phase]

    async def update_stats(self, message: RecordsProcessingStatsMessage):
        """Update progress bars based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, processing_stats in current_profile_run.phase_infos.items():
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
            self.debug(
                lambda: f"No message mapping found for message: {message.message_type}"
            )

    async def update_worker_health(self, message: WorkerHealthMessage) -> None:
        """Update the worker health."""
        self.trace(lambda: f"Worker health updated: {message}")

    async def update_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Update progress bars based on current credit phase."""
        self.debug(lambda: f"Credit phase {message.phase} completed")

        if message.phase in self.tqdm_requests:
            self.tqdm_requests[message.phase].close()
            del self.tqdm_requests[message.phase]

        if message.phase in self.tqdm_records:
            self.tqdm_records[message.phase].close()
            del self.tqdm_records[message.phase]

    async def update_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Update progress bars based on current credit phase."""
        self.debug(lambda: f"Credit phase {message.phase} started")
        phase = message.phase

        # Close any existing tqdm for this phase
        if phase in self.tqdm_requests:
            self.tqdm_requests[phase].close()
            del self.tqdm_requests[phase]

        if phase in self.tqdm_records:
            self.tqdm_records[phase].close()
            del self.tqdm_records[phase]

    async def update_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Update progress bars based on current credit phase."""
        await self.update_progress()

    async def update_results(self, message: ProfileResultsMessage):
        self.debug(lambda: f"Profile results updated: {message.records}")

    async def cleanup(self):
        """Clean up all progress bars."""

        for _, tqdm_bar in list(self.tqdm_requests.items()):
            tqdm_bar.close()
        self.tqdm_requests.clear()

        for _, tqdm_bar in list(self.tqdm_records.items()):
            tqdm_bar.close()
        self.tqdm_records.clear()
