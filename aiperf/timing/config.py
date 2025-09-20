# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import (
    UserConfig,
)
from aiperf.common.enums import RequestRateMode, TimingMode
from aiperf.common.models import AIPerfBaseModel


class TimingManagerConfig(AIPerfBaseModel):
    """Configuration for the timing manager."""

    timing_mode: TimingMode
    concurrency: int | None
    request_rate: float | None
    request_rate_mode: RequestRateMode
    request_count: int | None
    warmup_request_count: int
    benchmark_duration: float | None
    random_seed: int | None
    auto_offset_timestamps: bool
    fixed_schedule_start_offset: int | None
    fixed_schedule_end_offset: int | None

    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> "TimingManagerConfig":
        """Create a TimingManagerConfig from a UserConfig."""

        return cls(
            timing_mode=user_config.timing_mode,
            concurrency=user_config.loadgen.concurrency,
            request_rate=user_config.loadgen.request_rate,
            request_rate_mode=user_config.loadgen.request_rate_mode,
            request_count=user_config.loadgen.request_count,
            warmup_request_count=user_config.loadgen.warmup_request_count,
            benchmark_duration=user_config.loadgen.benchmark_duration,
            random_seed=user_config.input.random_seed,
            auto_offset_timestamps=user_config.input.fixed_schedule_auto_offset,
            fixed_schedule_start_offset=user_config.input.fixed_schedule_start_offset,
            fixed_schedule_end_offset=user_config.input.fixed_schedule_end_offset,
        )
