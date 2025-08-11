# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import Field

from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import (
    CreditPhase,
)
from aiperf.common.hooks import on_records_progress, on_requests_phase_progress
from aiperf.common.models import AIPerfBaseModel
from aiperf.common.models.progress_models import RecordsStats, RequestsStats
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.ui.base_ui import BaseAIPerfUI


class LoggerTracker(AIPerfBaseModel):
    """Tracker for the logger."""

    prev_records: dict[CreditPhase, int] = Field(default_factory=dict)
    prev_requests: dict[CreditPhase, int] = Field(default_factory=dict)

    def update_records(self, phase: CreditPhase, records: int) -> int:
        """Update the tracker with new records."""
        delta = records - self.prev_records.get(phase, 0)
        self.prev_records[phase] = records
        return delta

    def update_requests(self, phase: CreditPhase, requests: int) -> int:
        """Update the tracker with new requests."""
        delta = requests - self.prev_requests.get(phase, 0)
        self.prev_requests[phase] = requests
        return delta


@implements_protocol(AIPerfUIProtocol)
# @AIPerfUIFactory.register(AIPerfUIType.LOG)
class SimpleProgressLogger(BaseAIPerfUI):
    """Simple logger for progress updates. It will log the progress to the console.

    This is a fallback UI for when no other UI is available, or the user wants no-frills progress logging.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tracker = LoggerTracker()

    @on_records_progress
    def _on_records_progress(self, records_stats: RecordsStats):
        """Log the progress of the records."""
        self.info(lambda: f"Records progress: {records_stats}")

    @on_requests_phase_progress
    def _on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ):
        """Log the progress of the requests."""
        self.info(lambda: f"Requests {phase.capitalize()} progress: {requests_stats}")

    # async def update_progress(self):
    #     """Log a progress update based on current credit phase."""

    #     for phase, phase_stats in current_profile_run.phase_infos.items():
    #         total_requests = phase_stats.total_expected_requests or 0
    #         completed_requests = phase_stats.completed
    #         requests_delta = self.tracker.update_requests(phase, completed_requests)

    #         if requests_delta == 0 or total_requests == 0:
    #             continue

    #         self.info(
    #             lambda phase=phase,
    #             completed=completed_requests,
    #             per_sec=phase_stats.requests_per_second,
    #             eta=phase_stats.requests_eta,
    #             total=total_requests: f"Phase '{phase.capitalize()}' - Requests Completed: {completed} / {total} ({per_sec:.2f} requests/s, ~{format_duration(eta)} remaining)"
    #         )
