#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel

class WorkerPhaseTaskStats(AIPerfBaseModel):
    total: int
    failed: int
    completed: int
    @property
    def in_progress(self) -> int: ...
