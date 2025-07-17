#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from enum import Enum

from aiperf.common.enums.base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class MetricTimeType(CaseInsensitiveStrEnum):
    NANOSECONDS = "nanoseconds"
    MILLISECONDS = "milliseconds"
    SECONDS = "seconds"
    def short_name(self) -> str: ...

class MetricType(Enum):
    METRIC_OF_RECORDS = ...
    METRIC_OF_METRICS = ...
    METRIC_OF_BOTH = ...
