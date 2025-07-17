#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_REGISTRATION_SECONDS as DEFAULT_WAIT_FOR_REGISTRATION_SECONDS,
)
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_START_SECONDS as DEFAULT_WAIT_FOR_START_SECONDS,
)
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_STOP_SECONDS as DEFAULT_WAIT_FOR_STOP_SECONDS,
)
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.messages import BaseServiceMessage as BaseServiceMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.services.service_manager.base import (
    BaseServiceManager as BaseServiceManager,
)
from aiperf.services.service_registry import (
    GlobalServiceRegistry as GlobalServiceRegistry,
)

class ServiceKubernetesRunInfo(AIPerfBaseModel):
    pod_name: str
    node_name: str
    namespace: str

class KubernetesServiceManager(BaseServiceManager):
    registry: Incomplete
    def __init__(
        self, required_services: dict[ServiceType, int], config: ServiceConfig
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
