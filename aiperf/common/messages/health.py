# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from typing import Literal

from pydantic import Field

from aiperf.common.credit_models import CreditPhase
from aiperf.common.enums import MessageType
from aiperf.common.messages.base import BaseServiceMessage
from aiperf.common.worker_models import ProcessHealth, WorkerPhaseTaskStats


class WorkerHealthMessage(BaseServiceMessage):
    """Message for a worker health check."""

    message_type: Literal[MessageType.WORKER_HEALTH] = MessageType.WORKER_HEALTH

    # override request_ns to be auto-filled if not provided
    request_ns: int = Field(  # type: ignore
        default_factory=time.time_ns,
        description="Timestamp of the request",
    )

    process: ProcessHealth = Field(..., description="The health of the worker process")

    # Worker specific fields
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats] = Field(
        ...,
        description="Stats for the tasks that have been sent to the worker, keyed by the credit phase",
    )
