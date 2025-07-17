#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.exceptions import InvalidStateError as InvalidStateError
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel

class CreditPhaseConfig(AIPerfBaseModel):
    type: CreditPhase
    total_expected_requests: int | None
    expected_duration_sec: float | None
    @property
    def is_time_based(self) -> bool: ...
    @property
    def is_request_count_based(self) -> bool: ...
    @property
    def is_valid(self) -> bool: ...

class CreditPhaseStats(CreditPhaseConfig):
    start_ns: int | None
    sent_end_ns: int | None
    end_ns: int | None
    sent: int
    completed: int
    @property
    def is_sending_complete(self) -> bool: ...
    @property
    def is_complete(self) -> bool: ...
    @property
    def is_started(self) -> bool: ...
    @property
    def in_flight(self) -> int: ...
    @property
    def should_send(self) -> bool: ...
    @property
    def progress_percent(self) -> float | None: ...
    @classmethod
    def from_phase_config(cls, phase_config: CreditPhaseConfig) -> CreditPhaseStats: ...

class PhaseProcessingStats(AIPerfBaseModel):
    processed: int
    errors: int
    total_expected_requests: int | None
    @property
    def total_records(self) -> int: ...
