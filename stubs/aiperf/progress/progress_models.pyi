#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.aiperf_logger import AIPerfLogger as AIPerfLogger
from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.credit_models import CreditPhaseStats as CreditPhaseStats
from aiperf.common.credit_models import PhaseProcessingStats as PhaseProcessingStats
from aiperf.common.enums import BenchmarkSuiteType as BenchmarkSuiteType
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.messages import ProfileResultsMessage as ProfileResultsMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.worker_models import WorkerPhaseTaskStats as WorkerPhaseTaskStats

logger: Incomplete

class CreditPhaseComputedStats(AIPerfBaseModel):
    requests_per_second: float | None
    requests_eta: float | None
    requests_update_ns: int | None
    records_per_second: float | None
    records_eta: float | None
    records_update_ns: int | None

class FullCreditPhaseProgressInfo(
    CreditPhaseStats, PhaseProcessingStats, CreditPhaseComputedStats
):
    last_record_update_ns: int | None
    worker_processing_stats: dict[str, PhaseProcessingStats]
    last_request_update_ns: int | None
    worker_request_stats: dict[str, WorkerPhaseTaskStats]
    @property
    def elapsed_time(self) -> float | None: ...

class ProfileRunProgress(AIPerfBaseModel):
    profile_id: str | None
    start_ns: int | None
    end_ns: int | None
    last_update_ns: int | None
    active_phase: CreditPhase | None
    phase_infos: dict[CreditPhase, FullCreditPhaseProgressInfo]
    profile_results: ProfileResultsMessage | None
    was_cancelled: bool
    @property
    def is_started(self) -> bool: ...
    @property
    def is_complete(self) -> bool: ...
    @property
    def requests_completed(self) -> int | None: ...
    @property
    def requests_processed(self) -> int | None: ...
    @property
    def request_errors(self) -> int | None: ...
    @property
    def requests_per_second(self) -> float | None: ...
    @property
    def requests_eta(self) -> float | None: ...
    @property
    def processed_per_second(self) -> float | None: ...
    @property
    def processing_eta(self) -> float | None: ...
    @property
    def elapsed_time(self) -> float | None: ...
    @property
    def eta(self) -> float | None: ...

class BenchmarkSuiteProgress(AIPerfBaseModel):
    type: BenchmarkSuiteType
    start_ns: int | None
    end_ns: int | None
    profile_runs: list[ProfileRunProgress]
    current_profile_run: ProfileRunProgress | None
