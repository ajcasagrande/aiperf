# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from tqdm import tqdm

from aiperf.common.enums import CreditPhase
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
        current_profile_run = self.progress_tracker.current_profile_run
        active_phase = self.progress_tracker.active_credit_phase

        if current_profile_run is None or active_phase is None:
            return

        if active_phase not in current_profile_run.phases:
            return

        phase_stats = current_profile_run.phases[active_phase]
        total_requests = phase_stats.total or 0
        completed_requests = phase_stats.completed

        self.logger.debug(
            "Phase %s - Requests Completed: %d / %d",
            active_phase,
            completed_requests,
            total_requests,
        )

        # Only create tqdm if we have a valid total > 0
        if active_phase not in self.tqdm_requests and total_requests > 0:
            self.tqdm_requests[active_phase] = tqdm(
                total=total_requests,
                desc=f"Requests ({active_phase.value})",
                colour="green",
            )

        if active_phase in self.tqdm_requests:
            self.tqdm_requests[active_phase].n = completed_requests
            self.tqdm_requests[active_phase].refresh()

        # Close tqdm when completed
        if (
            total_requests > 0
            and completed_requests >= total_requests
            and active_phase in self.tqdm_requests
        ):
            self.tqdm_requests[active_phase].close()
            del self.tqdm_requests[active_phase]

    async def update_stats(self):
        """Log a stats update based on current credit phase."""
        current_profile_run = self.progress_tracker.current_profile_run
        active_phase = self.progress_tracker.active_credit_phase

        if current_profile_run is None or active_phase is None:
            return

        if active_phase not in current_profile_run.processing_stats:
            return

        processing_stats = current_profile_run.processing_stats[active_phase]
        phase_stats = current_profile_run.phases.get(active_phase)
        total_requests = phase_stats.total if phase_stats else 0
        processed_requests = processing_stats.processed

        self.logger.debug(
            "Phase %s - Records Processed: %d / %d",
            active_phase,
            processed_requests,
            total_requests,
        )

        # Only create tqdm if we have a valid total > 0
        if active_phase not in self.tqdm_records and total_requests > 0:
            self.tqdm_records[active_phase] = tqdm(
                total=total_requests,
                desc=f"Records ({active_phase.value})",
                colour="blue",
            )

        if active_phase in self.tqdm_records:
            self.tqdm_records[active_phase].n = processed_requests
            self.tqdm_records[active_phase].refresh()

        # Close tqdm when completed
        if (
            total_requests > 0
            and processed_requests >= total_requests
            and active_phase in self.tqdm_records
        ):
            self.logger.debug(
                "Phase %s - Closing TQDM. Records Processed: %d / %d",
                active_phase,
                processed_requests,
                total_requests,
            )
            self.tqdm_records[active_phase].close()
            del self.tqdm_records[active_phase]

    async def update_credit_phase_complete(self, phase: CreditPhase):
        """Log a credit phase complete update."""
        self.logger.debug("Credit phase %s completed", phase)

        if phase in self.tqdm_requests:
            self.tqdm_requests[phase].close()
            del self.tqdm_requests[phase]

        if phase in self.tqdm_records:
            self.tqdm_records[phase].close()
            del self.tqdm_records[phase]

    async def update_credit_phase_start(self, phase: CreditPhase):
        """Log a credit phase start update."""
        self.logger.debug("Credit phase %s started", phase)

        # Close any existing tqdm for this phase
        if phase in self.tqdm_requests:
            self.tqdm_requests[phase].close()
            del self.tqdm_requests[phase]

        if phase in self.tqdm_records:
            self.tqdm_records[phase].close()
            del self.tqdm_records[phase]

    async def update_credit_phase_progress(self, phase: CreditPhase):
        """Log a credit phase progress update."""
        self.logger.debug("Credit phase %s progress updated", phase)

        # This will be handled by update_progress() which is called regularly
        await self.update_progress()

    async def update_results(self):
        """Log a results update."""
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
        for phase, tqdm_bar in list(self.tqdm_requests.items()):
            tqdm_bar.close()
        self.tqdm_requests.clear()

        for phase, tqdm_bar in list(self.tqdm_records.items()):
            tqdm_bar.close()
        self.tqdm_records.clear()
