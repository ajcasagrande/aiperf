#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod

from aiperf.common.enums import ServiceState as ServiceState
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.messages import Message as Message

class BaseServiceInterface(ABC, metaclass=abc.ABCMeta):
    @property
    @abstractmethod
    def service_type(self) -> ServiceType: ...
    @abstractmethod
    async def set_state(self, state: ServiceState) -> None: ...
    @abstractmethod
    async def initialize(self) -> None: ...
    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    async def configure(self, message: Message) -> None: ...
    @abstractmethod
    async def run_forever(self) -> None: ...
