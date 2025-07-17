#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config.config_defaults import (
    LoadGeneratorDefaults as LoadGeneratorDefaults,
)
from aiperf.common.config.config_defaults import ServiceDefaults as ServiceDefaults
from aiperf.common.config.user_config import UserConfig as UserConfig
from aiperf.common.enums import RequestRateMode as RequestRateMode
from aiperf.common.enums import TimingMode as TimingMode
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel

class TimingManagerConfig(AIPerfBaseModel):
    timing_mode: TimingMode
    concurrency: int
    request_rate: float | None
    request_rate_mode: RequestRateMode
    request_count: int
    warmup_request_count: int
    random_seed: int | None
    progress_report_interval_sec: float
    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> TimingManagerConfig: ...
