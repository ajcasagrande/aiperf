#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class SSEFieldType(CaseInsensitiveStrEnum):
    DATA = "data"
    EVENT = "event"
    ID = "id"
    RETRY = "retry"
    COMMENT = "comment"

class SSEEventType(CaseInsensitiveStrEnum):
    ERROR = "error"
    LLM_METRICS = "llm_metrics"
