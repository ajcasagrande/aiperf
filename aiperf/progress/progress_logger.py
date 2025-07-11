# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from tqdm import tqdm

from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    Message,
    RecordsProcessingStatsMessage,
)
from aiperf.common.worker_models import WorkerHealthMessage
from aiperf.progress.progress_tracker import ProgressTracker


class SimpleProgressLogger:
    """Simple logger for progress updates. It will use tqdm to show a progress bar."""

    def __init__(self, progress_tracker: ProgressTracker):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.progress_tracker = progress_tracker
        self.tqdm_requests: dict[CreditPhase, tqdm] = {}
        self.tqdm_records: dict[CreditPhase, tqdm] = {}

    async def update_progress(self):
        """Log a progress update based on current credit phase."""
        return
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, phase_stats in current_profile_run.phases.items():
            total_requests = phase_stats.total or 0
            completed_requests = phase_stats.completed

            self.logger.debug(
                "Phase %s - Requests Completed: %d / %d",
                phase,
                completed_requests,
                total_requests,
            )

            # Only create tqdm if we have a valid total > 0
            if phase not in self.tqdm_requests and total_requests > 0:
                self.tqdm_requests[phase] = tqdm(
                    total=total_requests,
                    desc=f"Requests ({phase.value})",
                    colour="green",
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
        return
        current_profile_run = self.progress_tracker.current_profile_run

        if current_profile_run is None:
            return

        for phase, processing_stats in current_profile_run.processing_stats.items():
            processed_records = processing_stats.processed
            total_records = processing_stats.total

        self.logger.debug(
            "Phase %s - Records Processed: %d / %d",
            phase,
            processed_records,
            total_records,
        )

        # Only create tqdm if we have a valid total > 0
        if phase not in self.tqdm_records and total_records > 0:
            self.tqdm_records[phase] = tqdm(
                total=total_records,
                desc=f"Records ({phase.value})",
                colour="blue",
            )

        if phase in self.tqdm_records:
            self.tqdm_records[phase].n = processed_records
            self.tqdm_records[phase].refresh()

        # Close tqdm when completed
        if (
            total_requests > 0
            and processed_records >= total_records
            and phase in self.tqdm_records
        ):
            self.logger.debug(
                "Phase %s - Closing TQDM. Records Processed: %d / %d",
                phase,
                processed_records,
                total_records,
            )
            self.tqdm_records[phase].close()
            del self.tqdm_records[phase]

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        return
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
        self.logger.debug("Credit phase %s completed", message.phase_stats.type)

        if message.phase_stats.type in self.tqdm_requests:
            self.tqdm_requests[message.phase_stats.type].close()
            del self.tqdm_requests[message.phase_stats.type]

        if message.phase_stats.type in self.tqdm_records:
            self.tqdm_records[message.phase_stats.type].close()
            del self.tqdm_records[message.phase_stats.type]

    async def update_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Log a credit phase start update."""
        self.logger.debug("Credit phase %s started", message.phase_stats.type)
        phase = message.phase_stats.type

        # Close any existing tqdm for this phase
        if phase in self.tqdm_requests:
            self.tqdm_requests[phase].close()
            del self.tqdm_requests[phase]

        if phase in self.tqdm_records:
            self.tqdm_records[phase].close()
            del self.tqdm_records[phase]

    async def update_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Log a credit phase progress update."""
        return
        self.logger.debug(
            "Credit phase %s progress updated", message.phase_stats_map.keys()
        )

        # This will be handled by update_progress() which is called regularly
        await self.update_progress()

    async def update_results(self):
        """Log a results update."""
        return
        self.logger.debug("Profile results updated")

        # Close all tqdm bars
        for phase, tqdm_bar in list(self.tqdm_requests.items()):
            tqdm_bar.close()
        self.tqdm_requests.clear()

        for phase, tqdm_bar in list(self.tqdm_records.items()):
            tqdm_bar.close()
        self.tqdm_records.clear()

    def cleanup(self):
        """Clean up all progress bars."""
        return
        for phase, tqdm_bar in list(self.tqdm_requests.items()):
            tqdm_bar.close()
        self.tqdm_requests.clear()

        for phase, tqdm_bar in list(self.tqdm_records.items()):
            tqdm_bar.close()
        self.tqdm_records.clear()
