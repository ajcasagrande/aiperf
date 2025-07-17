#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import NamedTuple

from _typeshed import Incomplete

from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel

class IOCounters(NamedTuple):
    read_count: Incomplete
    write_count: Incomplete
    read_bytes: Incomplete
    write_bytes: Incomplete
    read_chars: Incomplete
    write_chars: Incomplete

class CPUTimes(NamedTuple):
    user: Incomplete
    system: Incomplete
    iowait: Incomplete

class CtxSwitches(NamedTuple):
    voluntary: Incomplete
    involuntary: Incomplete

class ProcessHealth(AIPerfBaseModel):
    pid: int | None
    create_time: float
    uptime: float
    cpu_usage: float
    memory_usage: float
    io_counters: IOCounters | tuple | None
    cpu_times: CPUTimes | tuple | None
    num_ctx_switches: CtxSwitches | tuple | None
    num_threads: int | None
