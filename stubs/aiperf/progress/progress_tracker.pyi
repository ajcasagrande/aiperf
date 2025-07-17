#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages import (
    CreditPhaseCompleteMessage as CreditPhaseCompleteMessage,
)
from aiperf.common.messages import (
    CreditPhaseProgressMessage as CreditPhaseProgressMessage,
)
from aiperf.common.messages import CreditPhaseStartMessage as CreditPhaseStartMessage
from aiperf.common.messages import Message as Message
from aiperf.common.messages import ProfileResultsMessage as ProfileResultsMessage
from aiperf.common.messages import (
    RecordsProcessingStatsMessage as RecordsProcessingStatsMessage,
)
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.messages._credit import (
    CreditPhaseSendingCompleteMessage as CreditPhaseSendingCompleteMessage,
)
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.progress.progress_models import (
    BenchmarkSuiteProgress as BenchmarkSuiteProgress,
)
from aiperf.progress.progress_models import (
    FullCreditPhaseProgressInfo as FullCreditPhaseProgressInfo,
)
from aiperf.progress.progress_models import PhaseProcessingStats as PhaseProcessingStats
from aiperf.progress.progress_models import ProfileRunProgress as ProfileRunProgress

class ProgressTracker(AIPerfLoggerMixin):
    suite: BenchmarkSuiteProgress | None
    def __init__(self, **kwargs) -> None: ...
    def configure(
        self, suite: BenchmarkSuiteProgress, current_profile_run: ProfileRunProgress
    ): ...
    @property
    def current_profile_run(self) -> ProfileRunProgress | None: ...
    @property
    def active_phase(self) -> CreditPhase | None: ...
    @active_phase.setter
    def active_phase(self, value: CreditPhase): ...
    @property
    def phase_infos(self) -> dict[CreditPhase, FullCreditPhaseProgressInfo]: ...
    def get_phase_progress_info(
        self, phase: CreditPhase
    ) -> FullCreditPhaseProgressInfo | None: ...
    def get_phase_progress_info_or_warn(
        self, phase: CreditPhase
    ) -> FullCreditPhaseProgressInfo | None: ...
    def on_message(self, message: Message): ...
    def on_credit_phase_start(self, message: CreditPhaseStartMessage): ...
    def on_credit_phase_progress(self, message: CreditPhaseProgressMessage): ...
    def on_credit_phase_sending_complete(
        self, message: CreditPhaseSendingCompleteMessage
    ): ...
    def on_credit_phase_complete(self, message: CreditPhaseCompleteMessage): ...
    def on_phase_processing_stats(self, message: RecordsProcessingStatsMessage): ...
    def on_worker_health(self, message: WorkerHealthMessage): ...
    profile_results: Incomplete
    def on_profile_results(self, message: ProfileResultsMessage): ...
    def update_requests_stats(
        self, phase_info: FullCreditPhaseProgressInfo, request_ns: int
    ): ...
    def update_records_stats(
        self,
        phase_info: FullCreditPhaseProgressInfo,
        request_ns: int,
        stats: PhaseProcessingStats,
    ): ...
