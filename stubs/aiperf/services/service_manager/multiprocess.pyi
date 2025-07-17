#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import multiprocessing
from multiprocessing import Process
from multiprocessing.context import ForkProcess, SpawnProcess

from _typeshed import Incomplete

from aiperf.common.bootstrap import (
    bootstrap_and_run_service as bootstrap_and_run_service,
)
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_REGISTRATION_SECONDS as DEFAULT_WAIT_FOR_REGISTRATION_SECONDS,
)
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_START_SECONDS as DEFAULT_WAIT_FOR_START_SECONDS,
)
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_STOP_SECONDS as DEFAULT_WAIT_FOR_STOP_SECONDS,
)
from aiperf.common.constants import (
    GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS as GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
)
from aiperf.common.constants import (
    TASK_CANCEL_TIMEOUT_SHORT as TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.enums._message import MessageType as MessageType
from aiperf.common.enums._service import ServiceState as ServiceState
from aiperf.common.exceptions import ServiceTimeoutError as ServiceTimeoutError
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.messages import BaseServiceMessage as BaseServiceMessage
from aiperf.common.messages._error import (
    BaseServiceErrorMessage as BaseServiceErrorMessage,
)
from aiperf.common.messages._service import HeartbeatMessage as HeartbeatMessage
from aiperf.common.messages._service import RegistrationMessage as RegistrationMessage
from aiperf.common.messages._service import StatusMessage as StatusMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.services.service_manager.base import (
    BaseServiceManager as BaseServiceManager,
)
from aiperf.services.service_registry import (
    GlobalServiceRegistry as GlobalServiceRegistry,
)

class MultiProcessRunInfo(AIPerfBaseModel):
    model_config: Incomplete
    process: Process | SpawnProcess | ForkProcess | None
    service_type: ServiceType

class MultiProcessServiceManager(BaseServiceManager):
    multi_process_info: list[MultiProcessRunInfo]
    log_queue: Incomplete
    user_config: Incomplete
    registry: Incomplete
    registered_events: dict[ServiceType, asyncio.Event]
    state_events: dict[ServiceType, dict[ServiceState, asyncio.Event]]
    def __init__(
        self,
        required_services: dict[ServiceType, int],
        config: ServiceConfig,
        user_config: UserConfig | None = None,
        log_queue: multiprocessing.Queue | None = None,
    ) -> None: ...
    async def run_all_services(self) -> None: ...
    async def shutdown_all_services(self) -> None: ...
    async def kill_all_services(self) -> None: ...
    async def wait_for_all_services_registration(
        self, timeout_seconds: float = ...
    ) -> None: ...
    async def wait_for_all_services_to_start(
        self, timeout_seconds: float = ...
    ) -> None: ...
    async def wait_for_all_services_to_stop(
        self, timeout_seconds: float = ...
    ) -> None: ...
    async def on_message(self, message: BaseServiceMessage) -> None: ...
