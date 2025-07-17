#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any, Literal

from pydantic import SerializeAsAny as SerializeAsAny

from aiperf.common.config._user import UserConfig as UserConfig
from aiperf.common.enums import CommandType as CommandType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums._command import CommandResponseStatus as CommandResponseStatus
from aiperf.common.enums._service import ServiceType as ServiceType
from aiperf.common.messages._base import BaseServiceMessage as BaseServiceMessage
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.models import ErrorDetails as ErrorDetails

class ProcessRecordsCommandData(AIPerfBaseModel):
    cancelled: bool

class CommandMessage(BaseServiceMessage):
    message_type: Literal[MessageType.COMMAND]
    command: CommandType
    command_id: str
    require_response: bool
    target_service_type: ServiceType | None
    target_service_id: str | None
    data: SerializeAsAny[UserConfig | ProcessRecordsCommandData | AIPerfBaseModel | Any]

class CommandResponseMessage(BaseServiceMessage):
    message_type: Literal[MessageType.COMMAND_RESPONSE]
    command: CommandType
    command_id: str
    status: CommandResponseStatus
    data: SerializeAsAny[AIPerfBaseModel | None]
    error: ErrorDetails | None
