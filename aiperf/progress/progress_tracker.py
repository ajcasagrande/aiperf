# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    Message,
    ProfileResultsMessage,
    RecordsProcessingStatsMessage,
    WorkerHealthMessage,
)
from aiperf.common.messages.credit import CreditPhaseSendingCompleteMessage
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.progress.progress_models import (
    BenchmarkSuiteProgress,
    FullCreditPhaseProgressInfo,
    PhaseProcessingStats,
    ProfileRunProgress,
)


class ProgressTracker(AIPerfLoggerMixin):
    """A progress tracker that tracks the progress of the entire benchmark suite."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.suite: BenchmarkSuiteProgress | None = None

    def configure(
        self, suite: BenchmarkSuiteProgress, current_profile_run: ProfileRunProgress
    ):
        """Configure the progress tracker with a benchmark suite."""
        self.suite = suite
        self.suite.current_profile_run = current_profile_run

    @property
    def current_profile_run(self) -> ProfileRunProgress | None:
        if self.suite is None:
            return None
        return self.suite.current_profile_run

    @property
    def active_credit_phase(self) -> CreditPhase | None:
        if self.current_profile_run is None:
            return None
        return self.current_profile_run.active_phase

    @active_credit_phase.setter
    def active_credit_phase(self, value: CreditPhase):
        if self.current_profile_run is None:
            return
        self.current_profile_run.active_phase = value

    @property
    def phases(self) -> dict[CreditPhase, FullCreditPhaseProgressInfo]:
        if self.current_profile_run is None or self.current_profile_run.phases is None:
            raise ValueError("Profile run is not started")
        return self.current_profile_run.phases

    def get_phase_progress_info(
        self, phase: CreditPhase
    ) -> FullCreditPhaseProgressInfo | None:
        if self.current_profile_run is None or self.current_profile_run.phases is None:
            return None
        return self.current_profile_run.phases.get(phase)

    def get_phase_progress_info_or_warn(
        self, phase: CreditPhase
    ) -> FullCreditPhaseProgressInfo | None:
        """Get phase progress info, logging a warning if not found."""
        phase_info = self.get_phase_progress_info(phase)
        if phase_info is None:
            self.warning(lambda: f"Phase {phase} not found in current profile run")
        return phase_info

    def on_message(self, message: Message):
        """Update the progress from a message."""
        if self.current_profile_run is None:
            self.debug(
                lambda: f"Received {message.message_type} message before profile run is started"
            )
            return

        _message_mappings = {
            MessageType.CREDIT_PHASE_START: self.on_credit_phase_start,
            MessageType.CREDIT_PHASE_PROGRESS: self.on_credit_phase_progress,
            MessageType.CREDIT_PHASE_COMPLETE: self.on_credit_phase_complete,
            MessageType.PROCESSING_STATS: self.on_phase_processing_stats,
            MessageType.WORKER_HEALTH: self.on_worker_health,
            MessageType.PROFILE_RESULTS: self.on_profile_results,
        }

        if message.message_type in _message_mappings:
            _message_mappings[message.message_type](message)
        else:
            self.debug(
                lambda: f"ProfileRunProgress: Received unsupported message type: {message.message_type}"
            )

    def on_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Update the progress from a credit phase start message."""
        self.active_phase = message.phase
        phase_info = FullCreditPhaseProgressInfo(
            type=message.phase,
            start_ns=message.start_ns,
            # Only one of the below would be set
            total_expected_requests=message.total_expected_requests,
            expected_duration_sec=message.expected_duration_sec,
        )
        self.phases[message.phase] = phase_info
        self.update_requests_stats(phase_info, message.start_ns)

    def on_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Update the progress from a credit phase progress message."""
        phase_info = self.get_phase_progress_info_or_warn(message.phase)
        if phase_info is None:
            return

        phase_info.sent = message.sent
        phase_info.completed = message.completed
        self.update_requests_stats(phase_info, message.request_ns)

    def on_credit_phase_sending_complete(
        self, message: CreditPhaseSendingCompleteMessage
    ):
        """Update the progress from a credit phase sending complete message."""
        phase_info = self.get_phase_progress_info_or_warn(message.phase)
        if phase_info is None:
            return

        phase_info.sent_end_ns = message.sent_end_ns
        self.update_requests_stats(phase_info, message.request_ns)

    def on_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Update the progress from a credit phase complete message."""
        phase_info = self.get_phase_progress_info_or_warn(message.phase)
        if phase_info is None:
            return

        phase_info.end_ns = message.end_ns
        # Just in case we did not get a progress report for the last credit
        phase_info.completed = phase_info.sent
        self.update_requests_stats(phase_info, message.request_ns)

    def on_phase_processing_stats(self, message: RecordsProcessingStatsMessage):
        """Update the progress from a phase processing stats message."""
        phase_info = self.get_phase_progress_info_or_warn(message.phase)
        if phase_info is None:
            return

        phase_info.processed = message.processing_stats.processed
        phase_info.errors = message.processing_stats.errors
        phase_info.last_record_update_ns = time.time_ns()

        for worker_id, worker_stats in message.worker_stats.items():
            phase_info.worker_processing_stats[worker_id] = worker_stats

        self.update_records_stats(
            phase_info, message.request_ns, message.processing_stats
        )

    def on_worker_health(self, message: WorkerHealthMessage):
        """Update the progress from a worker health message."""
        worker_id = message.service_id
        for phase, stats in message.task_stats.items():
            phase_info = self.get_phase_progress_info_or_warn(phase)
            if phase_info is None:
                continue
            phase_info.worker_request_stats[worker_id] = stats

    def on_profile_results(self, message: ProfileResultsMessage):
        """Update the progress from a profile results message."""
        self.profile_results = message

    def update_requests_stats(
        self, phase_info: FullCreditPhaseProgressInfo, request_ns: int
    ):
        """Update the requests stats based on the TimingManager stats."""
        phase_info.requests_update_ns = request_ns or time.time_ns()

        self.debug(
            lambda: f"Updating requests stats for phase {phase_info.type} {request_ns} {phase_info.start_ns} {time.time_ns()}"
        )

        if (
            phase_info.start_ns is not None
            and (diff_ns := (request_ns or time.time_ns()) - phase_info.start_ns) > 0
        ):
            dur_sec = diff_ns / NANOS_PER_SECOND
            phase_info.requests_per_second = phase_info.completed / dur_sec
            if pct := phase_info.progress_percent:
                pct_remaining = 100 - pct
                phase_info.requests_eta = pct_remaining / (pct / dur_sec)
            else:
                phase_info.requests_eta = None
        else:
            phase_info.requests_per_second = None
            phase_info.requests_eta = None

    def update_records_stats(
        self,
        phase_info: FullCreditPhaseProgressInfo,
        request_ns: int,
        stats: PhaseProcessingStats,
    ):
        """Update the records stats based on the RecordsManager stats."""
        phase_info.records_update_ns = request_ns or time.time_ns()

        if (
            phase_info.start_ns
            and (diff_ns := (request_ns or time.time_ns()) - phase_info.start_ns) > 0
        ):
            dur_sec = diff_ns / NANOS_PER_SECOND
            phase_info.records_per_second = stats.processed / dur_sec
            if phase_info.records_per_second and phase_info.total_expected_requests:
                phase_info.records_eta = (
                    phase_info.total_expected_requests - stats.processed
                ) / phase_info.records_per_second
            else:
                phase_info.records_eta = None
        else:
            phase_info.records_per_second = None
            phase_info.records_eta = None
