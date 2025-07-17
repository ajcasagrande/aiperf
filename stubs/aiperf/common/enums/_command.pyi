#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class CommandType(CaseInsensitiveStrEnum):
    SHUTDOWN = "shutdown"
    PROCESS_RECORDS = "process_records"
    PROFILE_CONFIGURE = "profile_configure"
    PROFILE_START = "profile_start"
    PROFILE_STOP = "profile_stop"
    PROFILE_CANCEL = "profile_cancel"

class CommandResponseStatus(CaseInsensitiveStrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
