#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class SystemState(CaseInsensitiveStrEnum):
    INITIALIZING = "initializing"
    CONFIGURING = "configuring"
    READY = "ready"
    PROFILING = "profiling"
    PROCESSING = "processing"
    STOPPING = "stopping"
    SHUTDOWN = "shutdown"
