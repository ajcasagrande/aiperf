# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Models for tracking the progress of the benchmark suite."""

import time

from pydantic import Field

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.models.credit_models import CreditPhaseStats, PhaseProcessingStats
from aiperf.common.models.worker_models import WorkerPhaseTaskStats


class FullCreditPhaseProgressInfo(CreditPhaseStats, PhaseProcessingStats):
    """Full state of the credit phase progress, including the progress of the phase, the processing stats, and the worker stats."""

    # Computed stats based on the TimingManager
    requests_per_second: float | None = Field(
        default=None, description="The average requests per second"
    )
    requests_eta: float | None = Field(
        default=None, description="The estimated time for all requests to be completed"
    )
    requests_update_ns: int | None = Field(
        default=None, description="The time of the last request update"
    )
    # Computed stats based on the RecordsManager
    records_per_second: float | None = Field(
        default=None, description="The average records processed per second"
    )
    records_eta: float | None = Field(
        default=None, description="The estimated time for all records to be processed"
    )
    records_update_ns: int | None = Field(
        default=None, description="The time of the last record update"
    )
    # Worker stats
    worker_processing_stats: dict[str, PhaseProcessingStats] = Field(
        default_factory=dict,
        description="The processing stats for each worker as reported by the RecordsManager (processed, errors)",
    )
    worker_request_stats: dict[str, WorkerPhaseTaskStats] = Field(
        default_factory=dict,
        description="The request stats for each worker as reported by the Workers (total, completed, failed)",
    )

    @property
    def elapsed_time(self) -> float | None:
        """Get the elapsed time."""
        if not self.start_ns:
            return None
        return (time.time_ns() - self.start_ns) / NANOS_PER_SECOND
