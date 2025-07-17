#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol, runtime_checkable

from aiperf.common.comms.base import PubClientProtocol
from aiperf.common.enums import CreditPhase
from aiperf.common.mixins import (
    AIPerfLoggerMixinProtocol,
    ProcessHealthMixin,
    ProcessHealthMixinProtocol,
)
from aiperf.common.models import WorkerPhaseTaskStats


@runtime_checkable
class WorkerHealthMixinRequirements(
    AIPerfLoggerMixinProtocol, ProcessHealthMixinProtocol, Protocol
):
    """WorkerHealthMixinRequirements is a protocol that provides the requirements needed for the WorkerHealthMixin."""

    health_check_interval: int
    service_id: str
    pub_client: PubClientProtocol
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats]


class WorkerHealthMixin(ProcessHealthMixin, WorkerHealthMixinRequirements):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not isinstance(self, WorkerHealthMixinRequirements):
            raise ValueError(
                "WorkerHealthMixin must be used in a class that conforms to WorkerHealthMixinRequirements"
            )
