#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.enums import BenchmarkSuiteType as BenchmarkSuiteType
from aiperf.common.enums import CommandType as CommandType
from aiperf.common.enums import SystemState as SystemState
from aiperf.progress.progress_tracker import (
    BenchmarkSuiteProgress as BenchmarkSuiteProgress,
)
from aiperf.progress.progress_tracker import ProfileRunProgress as ProfileRunProgress
from aiperf.services.system_controller.system_controller import (
    SystemController as SystemController,
)

class ProfileRunner:
    controller: Incomplete
    tracker: Incomplete
    logger: Incomplete
    was_cancelled: bool
    def __init__(self, controller: SystemController) -> None: ...
    async def run(self) -> None: ...
    @property
    def is_complete(self) -> bool: ...
    async def profile_completed(self) -> None: ...
    async def cancel_profile(self) -> None: ...
