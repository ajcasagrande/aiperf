# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import BenchmarkSuiteType
from aiperf.common.models import (
    ProfileProgressMessage,
    ProfileStatsMessage,
    SweepProgressMessage,
)
from aiperf.common.models.messages import ProfileResultsMessage
from aiperf.common.models.progress import (
    ProfileProgress,
    ProfileSuiteProgress,
    SweepProgress,
    SweepSuiteProgress,
)

logger = logging.getLogger(__name__)


class ProgressTracker:
    def __init__(self):
        self.suite: ProfileSuiteProgress | SweepSuiteProgress | None = None

    @property
    def current_sweep(self) -> SweepProgress | None:
        if self.suite is None or not isinstance(self.suite, SweepSuiteProgress):
            return None
        return self.suite.current_sweep

    @property
    def current_profile(self) -> ProfileProgress | None:
        if self.suite is None:
            return None
        return self.suite.current_profile

    def configure(self, suite_type: BenchmarkSuiteType) -> None:
        if suite_type in [
            BenchmarkSuiteType.SINGLE_PROFILE,
            BenchmarkSuiteType.MULTI_PROFILE,
        ]:
            self.suite = ProfileSuiteProgress()

        elif suite_type in [
            BenchmarkSuiteType.SINGLE_SWEEP,
            BenchmarkSuiteType.MULTI_SWEEP,
        ]:
            self.suite = SweepSuiteProgress()

    def update_profile_progress(self, message: ProfileProgressMessage) -> None:
        current_time_ns = time.time_ns()
        if self.suite is None or self.suite.current_profile is None:
            return

        profile = self.suite.current_profile

        if profile.start_time_ns is None:
            profile.start_time_ns = current_time_ns
            profile.total_expected_requests = message.total
            logger.info(f"Starting performance test: {message.total:,} total requests")

        profile.total_expected_requests = message.total
        profile.requests_completed = message.completed

        if not profile.is_complete:
            profile.requests_per_second = (
                message.completed
                / (current_time_ns - profile.start_time_ns)
                * NANOS_PER_SECOND
            )
            profile.elapsed_time = (
                current_time_ns - profile.start_time_ns
            ) / NANOS_PER_SECOND
            profile.eta = (
                (profile.total_expected_requests - profile.requests_completed)
                / profile.requests_per_second
                if profile.requests_per_second > 0
                else None
            )

    def update_profile_stats(self, message: ProfileStatsMessage) -> None:
        if self.suite is None or self.suite.current_profile is None:
            return

        current_time_ns = time.time_ns()
        profile = self.suite.current_profile
        profile.request_errors = message.error_count
        profile.successful_requests = message.completed - profile.request_errors
        profile.requests_processed = message.completed

        profile.worker_completed = message.worker_completed
        profile.worker_errors = message.worker_errors
        if (
            profile.total_expected_requests is not None
            and profile.requests_processed >= profile.total_expected_requests
        ):
            logger.info("Profile completed")
            profile.end_time_ns = current_time_ns
            profile.is_complete = True

        if not profile.is_complete:
            profile.processed_per_second = (
                message.completed
                / (current_time_ns - profile.start_time_ns)
                * NANOS_PER_SECOND
            )

    def update_profile_results(self, message: ProfileResultsMessage) -> None:
        if self.suite is None or self.suite.current_profile is None:
            return

        profile = self.suite.current_profile
        profile.end_time_ns = message.end_ns
        profile.was_cancelled = message.was_cancelled
        profile.elapsed_time = (
            profile.end_time_ns - profile.start_time_ns
        ) / NANOS_PER_SECOND
        profile.eta = None
        profile.requests_per_second = 0
        profile.records = message.records
        profile.errors_by_type = message.errors_by_type

    def update_sweep_progress(self, message: SweepProgressMessage) -> None:
        # TODO:
        if self.suite is None or self.suite.current_sweep is None:
            return
