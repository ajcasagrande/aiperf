#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config._user import UserConfig as UserConfig
from aiperf.common.enums._service import ServiceRunType as ServiceRunType
from aiperf.common.enums._service import ServiceType as ServiceType
from aiperf.common.logging import get_global_log_queue as get_global_log_queue
from aiperf.services.service_manager import BaseServiceManager as BaseServiceManager
from aiperf.services.service_manager.kubernetes import (
    KubernetesServiceManager as KubernetesServiceManager,
)
from aiperf.services.service_manager.multiprocess import (
    MultiProcessServiceManager as MultiProcessServiceManager,
)

class ServiceManagerMixin:
    service_manager: BaseServiceManager
    required_services: dict[ServiceType, int]
    def __init__(self, *args, **kwargs) -> None: ...
    def create_service_manager(
        self, service_config: ServiceConfig, user_config: UserConfig
    ) -> None: ...
    async def run_all_services(self) -> None: ...
    async def stop_all_services(self) -> None: ...
    async def kill_all_services(self) -> None: ...
