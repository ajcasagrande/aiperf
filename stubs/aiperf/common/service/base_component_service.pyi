#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from collections.abc import Awaitable
from collections.abc import Callable as Callable

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.enums import CommandResponseStatus as CommandResponseStatus
from aiperf.common.enums import CommandType as CommandType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceState as ServiceState
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.hooks import aiperf_task as aiperf_task
from aiperf.common.hooks import on_init as on_init
from aiperf.common.hooks import on_set_state as on_set_state
from aiperf.common.messages import CommandMessage as CommandMessage
from aiperf.common.messages import CommandResponseMessage as CommandResponseMessage
from aiperf.common.messages import HeartbeatMessage as HeartbeatMessage
from aiperf.common.messages import RegistrationMessage as RegistrationMessage
from aiperf.common.messages import StatusMessage as StatusMessage
from aiperf.common.record_models import ErrorDetails as ErrorDetails
from aiperf.common.service.base_service import BaseService as BaseService

class BaseComponentService(BaseService, metaclass=abc.ABCMeta):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None: ...
    async def send_heartbeat(self) -> None: ...
    async def register(self) -> None: ...
    async def process_command_message(self, message: CommandMessage) -> None: ...
    def register_command_callback(
        self, cmd: CommandType, callback: Callable[[CommandMessage], Awaitable[None]]
    ) -> None: ...
    def create_heartbeat_message(self) -> HeartbeatMessage: ...
    def create_registration_message(self) -> RegistrationMessage: ...
    def create_status_message(self, state: ServiceState) -> StatusMessage: ...
