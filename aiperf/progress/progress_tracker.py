# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhaseType
from aiperf.progress.progress_models import (
    BenchmarkSuiteType,
    ProcessingStatsMessage,
    ProfileProgress,
    ProfileProgressMessage,
    ProfileResultsMessage,
    ProfileSuiteProgress,
    SweepProgress,
    SweepProgressMessage,
    SweepSuiteProgress,
)


class ProgressTracker:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
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

    @property
    def active_credit_phase(self) -> CreditPhaseType | None:
        if self.current_profile is None:
            return None
        return self.current_profile.credit_phase

    def configure(self, suite_type: BenchmarkSuiteType) -> None:
        if suite_type in [
            BenchmarkSuiteType.SINGLE_PROFILE,
            BenchmarkSuiteType.MULTI_PROFILE,
        ]:
            self.suite = ProfileSuiteProgress(
                profiles=[
                    ProfileProgress(
                        profile_id="0",
                        total_expected_requests=0,
                    )
                ],
                total_profiles=1,
            )

        elif suite_type in [
            BenchmarkSuiteType.SINGLE_SWEEP,
            BenchmarkSuiteType.MULTI_SWEEP,
        ]:
            self.suite = SweepSuiteProgress(
                sweeps=[
                    SweepProgress(
                        sweep_id="0",
                        profiles=[
                            ProfileProgress(
                                profile_id="0",
                                total_expected_requests=0,
                            )
                        ],
                    )
                ],
                total_sweeps=1,
            )

    def update_profile_progress(self, message: ProfileProgressMessage) -> None:
        if message.credit_phase != CreditPhaseType.PROFILING:
            # TODO: handle warmup progress
            return

        current_time_ns = time.time_ns()
        if self.suite is None or self.suite.current_profile is None:
            return

        profile = self.suite.current_profile
        profile.credit_phase = message.credit_phase

        if message.start_ns == 0:
            self.logger.warning("Profile progress message has no start_ns")
            return

        if profile.start_time_ns is None:
            profile.start_time_ns = message.start_ns

            profile.total_expected_requests = message.total
            self.logger.info(
                "Starting performance test: %d total requests (start_ns: %d)",
                message.total,
                message.start_ns,
            )

        profile.total_expected_requests = message.total
        profile.requests_completed = message.completed
        profile.ramp_up_completed = message.ramp_up_completed

        # Store measurement start time for steady-state calculations
        if message.measurement_start_ns > 0:
            profile.measurement_start_time_ns = message.measurement_start_ns
        else:
            profile.measurement_start_time_ns = message.start_ns

        if message.completed < profile.total_expected_requests:
            # Calculate steady-state metrics using measurement start time and steady-state completed requests
            measurement_start_ns = (
                profile.measurement_start_time_ns or profile.start_time_ns
            )
            steady_state_completed = profile.steady_state_completed
            if current_time_ns > measurement_start_ns:
                profile.requests_per_second = (
                    steady_state_completed
                    / (current_time_ns - measurement_start_ns)
                    * NANOS_PER_SECOND
                )
            else:
                profile.requests_per_second = None

            # Calculate overall elapsed time using the original start time
            profile.elapsed_time = (
                current_time_ns - profile.start_time_ns
            ) / NANOS_PER_SECOND

            # Calculate ETA using steady-state rate and remaining steady-state requests
            steady_state_total = (
                profile.total_expected_requests - profile.ramp_up_completed
            )
            steady_state_remaining = steady_state_total - steady_state_completed
            profile.eta = (
                (
                    steady_state_remaining / profile.requests_per_second
                    if profile.requests_per_second and profile.requests_per_second > 0
                    else None
                )
                if profile.requests_per_second is not None
                else None
            )

    def update_processing_stats(self, message: ProcessingStatsMessage) -> None:
        if self.suite is None or self.suite.current_profile is None:
            self.logger.warning("No current profile to update processing stats")
            return

        current_time_ns = time.time_ns()
        profile = self.suite.current_profile
        profile.request_errors = message.error_count
        profile.successful_requests = message.completed - message.error_count
        profile.requests_processed = message.completed

        profile.worker_completed = message.worker_completed
        profile.worker_errors = message.worker_errors
        if (
            profile.total_expected_requests is not None
            and profile.total_expected_requests > 0
            and profile.credit_phase == CreditPhaseType.PROFILING
            and profile.start_time_ns is not None
            and profile.requests_processed >= profile.total_expected_requests
        ):
            self.logger.info("Profile completed")
            profile.end_time_ns = current_time_ns
            profile.is_complete = True

        if not profile.is_complete and profile.start_time_ns is not None:
            # Use measurement start time for processing rate calculation if available
            measurement_start_ns = (
                profile.measurement_start_time_ns or profile.start_time_ns
            )

            # Calculate processing rate using measurement start time and steady-state processed requests
            steady_state_processed = max(
                0, message.completed - profile.ramp_up_completed
            )
            if current_time_ns > measurement_start_ns:
                profile.processed_per_second = (
                    steady_state_processed
                    / (current_time_ns - measurement_start_ns)
                    * NANOS_PER_SECOND
                )
            else:
                profile.processed_per_second = None

            # Calculate processing ETA using steady-state processed requests
            steady_state_total = (
                profile.total_expected_requests - profile.ramp_up_completed
            )
            steady_state_remaining = steady_state_total - steady_state_processed
            profile.processing_eta = (
                (
                    steady_state_remaining / profile.processed_per_second
                    if profile.processed_per_second
                    and profile.processed_per_second > 0
                    and profile.total_expected_requests
                    else None
                )
                if profile.processed_per_second is not None
                else None
            )

    def update_profile_results(self, message: ProfileResultsMessage) -> None:
        if self.suite is None or self.suite.current_profile is None:
            return

        profile = self.suite.current_profile
        profile.end_time_ns = message.end_ns
        profile.was_cancelled = message.was_cancelled
        if profile.start_time_ns is not None and profile.end_time_ns is not None:
            profile.elapsed_time = (
                profile.end_time_ns - profile.start_time_ns
            ) / NANOS_PER_SECOND
        profile.eta = None
        profile.requests_per_second = 0
        profile.records = message.records
        profile.errors_by_type = message.errors_by_type

    def update_sweep_progress(self, message: SweepProgressMessage) -> None:
        """Update sweep progress with the provided message."""
        if self.suite is None or self.suite.current_sweep is None:
            return

        current_sweep = self.suite.current_sweep

        if current_sweep.start_time_ns is None:
            current_sweep.start_time_ns = message.sweep_start_ns
            self.logger.info("Starting sweep: %s", current_sweep.sweep_id)

        if message.end_ns is not None:
            current_sweep.end_time_ns = message.end_ns
            self.logger.info("Completed sweep: %s", current_sweep.sweep_id)
