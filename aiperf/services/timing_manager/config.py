# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

from pydantic import BaseModel

from aiperf.common.config.config_defaults import LoadGeneratorDefaults
from aiperf.common.config.user_config import UserConfig


class TimingMode(str, Enum):
    """Enum for the different timing modes."""

    FIXED_SCHEDULE = "fixed_schedule"
    CONCURRENCY = "concurrency"
    RATE = "rate"


class TimingManagerConfig(BaseModel):
    """Configuration for the timing manager."""

    timing_mode: TimingMode = TimingMode.CONCURRENCY
    concurrency: int = LoadGeneratorDefaults.CONCURRENCY
    request_rate: float | None = None
    request_count: int | None = None
    warmup_request_count: int | None = None

    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> "TimingManagerConfig":
        """Create a TimingManagerConfig from a UserConfig."""

        if user_config.input.file is not None:
            timing_mode = TimingMode.FIXED_SCHEDULE
        elif user_config.load.request_rate is not None:
            timing_mode = TimingMode.RATE
        else:
            timing_mode = TimingMode.CONCURRENCY  # Default to concurrency mode

        return cls(
            timing_mode=timing_mode,
            concurrency=user_config.load.concurrency,
            request_rate=user_config.load.request_rate,
            request_count=user_config.load.request_count,
            warmup_request_count=user_config.load.warmup_request_count,
        )
