#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import psutil

from aiperf.common.models import ProcessHealth as ProcessHealth

class ProcessHealthMixin:
    process: psutil.Process
    create_time: float
    process_health: ProcessHealth | None
    previous: ProcessHealth | None
    def __init__(self, **kwargs) -> None: ...
    def get_process_health(self) -> ProcessHealth: ...
