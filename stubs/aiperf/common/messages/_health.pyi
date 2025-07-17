#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages._base import BaseServiceMessage as BaseServiceMessage
from aiperf.common.models import CreditPhase as CreditPhase
from aiperf.common.models import ProcessHealth as ProcessHealth
from aiperf.common.models import WorkerPhaseTaskStats as WorkerPhaseTaskStats

class WorkerHealthMessage(BaseServiceMessage):
    message_type: Literal[MessageType.WORKER_HEALTH]
    process: ProcessHealth
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats]
    @property
    def total_tasks(self) -> int: ...
    @property
    def completed_tasks(self) -> int: ...
    @property
    def failed_tasks(self) -> int: ...
    @property
    def in_progress_tasks(self) -> int: ...
    @property
    def error_rate(self) -> float: ...
