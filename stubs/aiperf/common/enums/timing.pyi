#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class TimingMode(CaseInsensitiveStrEnum):
    FIXED_SCHEDULE = "fixed_schedule"
    CONCURRENCY = "concurrency"
    REQUEST_RATE = "request_rate"

class RequestRateMode(CaseInsensitiveStrEnum):
    CONSTANT = "constant"
    POISSON = "poisson"

class CreditPhase(CaseInsensitiveStrEnum):
    WARMUP = "warmup"
    PROFILING = "profiling"
