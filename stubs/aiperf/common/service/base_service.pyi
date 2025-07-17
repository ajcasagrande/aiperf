#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC

from _typeshed import Incomplete

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.enums import ServiceState as ServiceState
from aiperf.common.exceptions import AIPerfError as AIPerfError
from aiperf.common.exceptions import ServiceError as ServiceError
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.hooks import AIPerfTaskHook as AIPerfTaskHook
from aiperf.common.messages import Message as Message
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.mixins import AIPerfTaskMixin as AIPerfTaskMixin
from aiperf.common.mixins import EventBusClientMixin as EventBusClientMixin
from aiperf.common.mixins import ProcessHealthMixin as ProcessHealthMixin
from aiperf.common.mixins import supports_hooks as supports_hooks
from aiperf.common.service.base_service_interface import (
    BaseServiceInterface as BaseServiceInterface,
)

class BaseService(
    BaseServiceInterface,
    AIPerfTaskMixin,
    ProcessHealthMixin,
    EventBusClientMixin,
    AIPerfLoggerMixin,
    ABC,
    metaclass=abc.ABCMeta,
):
    service_id: str
    service_config: Incomplete
    user_config: Incomplete
    stop_event: Incomplete
    initialized_event: Incomplete
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None: ...
    @property
    def state(self) -> ServiceState: ...
    @property
    def is_initialized(self) -> bool: ...
    async def set_state(self, state: ServiceState) -> None: ...
    async def initialize(self) -> None: ...
    async def run_forever(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def configure(self, message: Message) -> None: ...
