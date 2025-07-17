#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod

from _typeshed import Incomplete

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_START_SECONDS as DEFAULT_WAIT_FOR_START_SECONDS,
)
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_STOP_SECONDS as DEFAULT_WAIT_FOR_STOP_SECONDS,
)
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.messages import BaseServiceMessage as BaseServiceMessage
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.models import ServiceRegistrationInfo as ServiceRegistrationInfo

class BaseServiceManager(AIPerfLoggerMixin, ABC, metaclass=abc.ABCMeta):
    required_services: Incomplete
    config: Incomplete
    service_map: dict[ServiceType, list[ServiceRegistrationInfo]]
    service_id_map: dict[str, ServiceRegistrationInfo]
    def __init__(
        self, required_services: dict[ServiceType, int], config: ServiceConfig
    ) -> None: ...
    @abstractmethod
    async def run_all_services(self) -> None: ...
    @abstractmethod
    async def shutdown_all_services(self) -> None: ...
    @abstractmethod
    async def kill_all_services(self) -> None: ...
    @abstractmethod
    async def wait_for_all_services_registration(
        self, timeout_seconds: float = ...
    ) -> None: ...
    @abstractmethod
    async def wait_for_all_services_to_start(
        self, timeout_seconds: float = ...
    ) -> None: ...
    @abstractmethod
    async def wait_for_all_services_to_stop(
        self, timeout_seconds: float = ...
    ) -> None: ...
    @abstractmethod
    async def on_message(self, message: BaseServiceMessage) -> None: ...
