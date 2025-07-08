# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from aiperf.common.config.config_defaults import LoadGeneratorDefaults
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CaseInsensitiveStrEnum, CreditPhaseType, RequestRateMode


class TimingMode(CaseInsensitiveStrEnum):
    """Enum for the different timing modes."""

    FIXED_SCHEDULE = "fixed_schedule"
    CONCURRENCY = "concurrency"
    REQUEST_RATE = "rate"


class TimingManagerConfig(BaseModel):
    """Configuration for the timing manager."""

    timing_mode: TimingMode = TimingMode.CONCURRENCY
    concurrency: int = LoadGeneratorDefaults.CONCURRENCY
    request_rate: float | None = LoadGeneratorDefaults.REQUEST_RATE
    request_rate_mode: RequestRateMode = LoadGeneratorDefaults.REQUEST_RATE_MODE
    request_count: int = LoadGeneratorDefaults.REQUEST_COUNT
    warmup_request_count: int = LoadGeneratorDefaults.WARMUP_REQUEST_COUNT
    concurrency_ramp_up_time: float | None = (
        LoadGeneratorDefaults.CONCURRENCY_RAMP_UP_TIME
    )
    random_seed: int | None = None

    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> "TimingManagerConfig":
        """Create a TimingManagerConfig from a UserConfig."""

        if user_config.input.file is not None:
            timing_mode = TimingMode.FIXED_SCHEDULE
        elif user_config.load.request_rate is not None:
            timing_mode = TimingMode.REQUEST_RATE
        else:
            timing_mode = TimingMode.CONCURRENCY  # Default to concurrency mode

        return cls(
            timing_mode=timing_mode,
            concurrency=user_config.load.concurrency,
            request_rate=user_config.load.request_rate,
            request_rate_mode=user_config.load.request_rate_mode,
            request_count=user_config.load.request_count,
            warmup_request_count=user_config.load.warmup_request_count,
            concurrency_ramp_up_time=user_config.load.concurrency_ramp_up_time,
            random_seed=user_config.input.random_seed,
        )


class CreditPhase(BaseModel):
    """
    A phase of credit issuing. Either a warmup phase or a profiling phase.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    phase_type: CreditPhaseType = Field(
        default=CreditPhaseType.PROFILING,
        description="The type of credit phase (either warmup or profiling)",
    )
    start_time_ns: int = Field(
        default=0, description="The start time of the phase in nanoseconds"
    )
    end_time_ns: int = Field(
        default=0, description="The end time of the phase in nanoseconds"
    )
    total_credits: int = Field(
        ..., gt=0, description="The total number of credits in the phase"
    )
    sent_credits: int = Field(
        default=0, description="The number of credits sent in the phase"
    )
    completed_credits: int = Field(
        default=0, description="The number of credits completed in the phase"
    )
    cancelled: bool = Field(
        default=False, description="Whether the phase was cancelled"
    )
    completed_event: asyncio.Event = Field(
        default_factory=asyncio.Event,
        description="An event that is set when the phase is completed",
    )
