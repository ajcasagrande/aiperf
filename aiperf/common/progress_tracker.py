# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import time
from collections.abc import Generator
from contextlib import contextmanager
from threading import Lock

from aiperf.common.config import ServiceConfig
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase, MessageType
from aiperf.common.hooks import on_message
from aiperf.common.messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseSendingCompleteMessage,
    CreditPhaseStartMessage,
    ProfileResultsMessage,
    RecordsProcessingStatsMessage,
    WorkerHealthMessage,
)
from aiperf.common.mixins import MessageBusClientMixin
from aiperf.common.models.credit_models import PhaseProcessingStats
from aiperf.common.models.progress_models import FullCreditPhaseProgressInfo


class ProgressTracker(MessageBusClientMixin):
    """A progress tracker that tracks the progress of the entire benchmark suite."""

    def __init__(self, service_config: ServiceConfig, **kwargs):
        super().__init__(service_config=service_config, **kwargs)
        self.phase_infos: dict[CreditPhase, FullCreditPhaseProgressInfo] = {}
        self.active_phase: CreditPhase | None = None
        self.phase_info_lock = Lock()

    @on_message(MessageType.CREDIT_PHASE_START)
    def on_credit_phase_start(self, message: CreditPhaseStartMessage):
        """Update the progress from a credit phase start message."""
        with self.phase_info_lock:
            if message.phase in self.phase_infos:
                self.warning(f"Phase stats already started for {message.phase}")
                return
            self.active_phase = message.phase
            phase_info = FullCreditPhaseProgressInfo(
                type=message.phase,
                start_ns=message.start_ns,
                # Only one of the below would be set
                total_expected_requests=message.total_expected_requests,
                expected_duration_sec=message.expected_duration_sec,
            )
            self.phase_infos[message.phase] = phase_info
            self.update_requests_stats(phase_info, message.start_ns)

    @on_message(MessageType.CREDIT_PHASE_PROGRESS)
    def on_credit_phase_progress(self, message: CreditPhaseProgressMessage):
        """Update the progress from a credit phase progress message."""
        with self.phase_progress_context(message.phase) as phase_info:
            phase_info.sent = message.sent
            phase_info.completed = message.completed
            self.update_requests_stats(phase_info, message.request_ns)

    @on_message(MessageType.CREDIT_PHASE_SENDING_COMPLETE)
    def on_credit_phase_sending_complete(
        self, message: CreditPhaseSendingCompleteMessage
    ):
        """Update the progress from a credit phase sending complete message."""
        with self.phase_progress_context(message.phase) as phase_info:
            phase_info.sent_end_ns = message.sent_end_ns
            self.update_requests_stats(phase_info, message.request_ns)

    @on_message(MessageType.CREDIT_PHASE_COMPLETE)
    def on_credit_phase_complete(self, message: CreditPhaseCompleteMessage):
        """Update the progress from a credit phase complete message."""
        with self.phase_progress_context(message.phase) as phase_info:
            phase_info.end_ns = message.end_ns
            # Just in case we did not get a progress report for the last credit (timing issues due to network)
            phase_info.completed = phase_info.sent
            self.update_requests_stats(phase_info, message.request_ns)

    @on_message(MessageType.PROCESSING_STATS)
    def on_phase_processing_stats(self, message: RecordsProcessingStatsMessage):
        """Update the progress from a phase processing stats message."""
        with self.phase_progress_context(CreditPhase.PROFILING) as phase_info:
            phase_info.processed = message.processing_stats.processed
            phase_info.errors = message.processing_stats.errors
            phase_info.records_update_ns = time.time_ns()

            for worker_id, worker_stats in message.worker_stats.items():
                phase_info.worker_processing_stats[worker_id] = worker_stats

            self.update_records_stats(
                phase_info, message.request_ns, message.processing_stats
            )

    @on_message(MessageType.WORKER_HEALTH)
    def on_worker_health(self, message: WorkerHealthMessage):
        """Update the progress from a worker health message."""
        worker_id = message.service_id
        for phase, stats in message.task_stats.items():
            with self.phase_progress_context(phase) as phase_info:
                phase_info.worker_request_stats[worker_id] = stats

    @on_message(MessageType.PROFILE_RESULTS)
    def on_profile_results(self, message: ProfileResultsMessage):
        """Update the progress from a profile results message."""
        self.profile_results = message

    def update_requests_stats(
        self, phase_info: FullCreditPhaseProgressInfo, request_ns: int | None
    ):
        """Update the requests stats based on the TimingManager stats."""
        phase_info.requests_update_ns = request_ns or time.time_ns()

        if self.is_debug_enabled:
            self.debug(
                f"Updating requests stats for phase '{phase_info.type.title()}': sent: {phase_info.sent}, completed: {phase_info.completed}, total_expected: {phase_info.total_expected_requests}"
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
        request_ns: int | None,
        stats: PhaseProcessingStats,
    ):
        """Update the records stats based on the RecordsManager stats."""
        phase_info.records_update_ns = request_ns or time.time_ns()

        if self.is_debug_enabled:
            self.debug(
                f"Updating records stats for phase '{phase_info.type.title()}': processed: {stats.processed}, errors: {stats.errors}"
            )

        diff_ns = 0
        if phase_info.start_ns:
            diff_ns = (request_ns or time.time_ns()) - phase_info.start_ns
        if diff_ns > 0:
            diff_sec = diff_ns / NANOS_PER_SECOND
            phase_info.records_per_second = stats.processed / diff_sec
            if pct := phase_info.progress_percent:
                pct_remaining = 100 - pct
                phase_info.records_eta = pct_remaining / (pct / diff_sec)
            else:
                phase_info.records_eta = None
        else:
            phase_info.records_per_second = None
            phase_info.records_eta = None

    @contextmanager
    def phase_progress_context(
        self, phase: CreditPhase
    ) -> Generator[FullCreditPhaseProgressInfo, None, None]:
        """Context manager for safely accessing phase progress info with warning."""
        with self.phase_info_lock:
            phase_info = self.phase_infos.get(phase)
            if phase_info is None:
                self.warning(
                    f"Phase '{phase.title()}' not found in current profile run"
                )
                return
            yield phase_info
