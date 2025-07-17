#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from aiperf.common.enums import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)

class BaseZMQProxyConfig(BaseModel, ABC, metaclass=abc.ABCMeta):
    @property
    @abstractmethod
    def frontend_address(self) -> str: ...
    @property
    @abstractmethod
    def backend_address(self) -> str: ...
    @property
    @abstractmethod
    def control_address(self) -> str | None: ...
    @property
    @abstractmethod
    def capture_address(self) -> str | None: ...

class BaseZMQCommunicationConfig(BaseModel, ABC, metaclass=abc.ABCMeta):
    event_bus_proxy_config: ClassVar[BaseZMQProxyConfig]
    dataset_manager_proxy_config: ClassVar[BaseZMQProxyConfig]
    raw_inference_proxy_config: ClassVar[BaseZMQProxyConfig]
    @property
    @abstractmethod
    def records_push_pull_address(self) -> str: ...
    @property
    @abstractmethod
    def credit_drop_address(self) -> str: ...
    @property
    @abstractmethod
    def credit_return_address(self) -> str: ...
    def get_address(self, address_type: CommunicationClientAddressType) -> str: ...

class ZMQTCPProxyConfig(BaseZMQProxyConfig):
    host: str
    frontend_port: int
    backend_port: int
    control_port: int | None
    capture_port: int | None
    @property
    def frontend_address(self) -> str: ...
    @property
    def backend_address(self) -> str: ...
    @property
    def control_address(self) -> str | None: ...
    @property
    def capture_address(self) -> str | None: ...

class ZMQIPCProxyConfig(BaseZMQProxyConfig):
    path: str
    name: str
    enable_control: bool
    enable_capture: bool
    @property
    def frontend_address(self) -> str: ...
    @property
    def backend_address(self) -> str: ...
    @property
    def control_address(self) -> str | None: ...
    @property
    def capture_address(self) -> str | None: ...

class ZMQTCPConfig(BaseZMQCommunicationConfig):
    host: str
    records_push_pull_port: int
    credit_drop_port: int
    credit_return_port: int
    dataset_manager_proxy_config: ZMQTCPProxyConfig
    event_bus_proxy_config: ZMQTCPProxyConfig
    raw_inference_proxy_config: ZMQTCPProxyConfig
    @property
    def records_push_pull_address(self) -> str: ...
    @property
    def credit_drop_address(self) -> str: ...
    @property
    def credit_return_address(self) -> str: ...

class ZMQIPCConfig(BaseZMQCommunicationConfig):
    path: str
    dataset_manager_proxy_config: ZMQIPCProxyConfig
    event_bus_proxy_config: ZMQIPCProxyConfig
    raw_inference_proxy_config: ZMQIPCProxyConfig
    @property
    def records_push_pull_address(self) -> str: ...
    @property
    def credit_drop_address(self) -> str: ...
    @property
    def credit_return_address(self) -> str: ...
