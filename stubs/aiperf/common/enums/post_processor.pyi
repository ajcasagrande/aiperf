#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class PostProcessorType(CaseInsensitiveStrEnum):
    METRIC_SUMMARY = "metric_summary"
