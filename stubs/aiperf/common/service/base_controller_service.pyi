#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config.user_config import UserConfig as UserConfig
from aiperf.common.enums import CommandType as CommandType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.hooks import on_run as on_run
from aiperf.common.messages import CommandMessage as CommandMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.service.base_service import BaseService as BaseService

class BaseControllerService(BaseService, metaclass=abc.ABCMeta):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None: ...
    def create_command_message(
        self,
        command: CommandType,
        target_service_id: str | None,
        target_service_type: ServiceType | None = None,
        data: AIPerfBaseModel | None = None,
    ) -> CommandMessage: ...
