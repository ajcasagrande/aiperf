#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from _typeshed import Incomplete

from aiperf.common.bootstrap import (
    bootstrap_and_run_service as bootstrap_and_run_service,
)
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.constants import (
    TASK_CANCEL_TIMEOUT_SHORT as TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceRunType as ServiceRunType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.exceptions import ConfigurationError as ConfigurationError
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import on_cleanup as on_cleanup
from aiperf.common.hooks import on_init as on_init
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.service.base_component_service import (
    BaseComponentService as BaseComponentService,
)
from aiperf.workers.worker import Worker as Worker

class WorkerProcessInfo(AIPerfBaseModel):
    model_config: Incomplete
    worker_id: str
    process: Any

class WorkerManager(BaseComponentService):
    workers: dict[str, WorkerProcessInfo]
    worker_health: dict[str, WorkerHealthMessage]
    cpu_count: Incomplete
    max_concurrency: Incomplete
    max_workers: Incomplete
    initial_workers: Incomplete
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...

def main() -> None: ...
