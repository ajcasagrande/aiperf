#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class BenchmarkSuiteCompletionTrigger(CaseInsensitiveStrEnum):
    COMPLETED_PROFILES = "completed_profiles"

class BenchmarkSuiteType(CaseInsensitiveStrEnum):
    SINGLE_PROFILE = "single_profile"

class ProfileCompletionTrigger(CaseInsensitiveStrEnum):
    REQUEST_COUNT = "request_count"
