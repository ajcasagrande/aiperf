#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import SerializeAsAny as SerializeAsAny

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import NotificationType as NotificationType
from aiperf.common.enums import ServiceState as ServiceState
from aiperf.common.messages._base import BaseServiceMessage as BaseServiceMessage
from aiperf.common.messages._base import BaseStatusMessage as BaseStatusMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel

class StatusMessage(BaseStatusMessage):
    message_type: Literal[MessageType.STATUS]

class RegistrationMessage(BaseStatusMessage):
    message_type: Literal[MessageType.REGISTRATION]
    state: ServiceState

class HeartbeatMessage(BaseStatusMessage):
    message_type: Literal[MessageType.HEARTBEAT]

class NotificationMessage(BaseServiceMessage):
    message_type: Literal[MessageType.NOTIFICATION]
    notification_type: NotificationType
    data: SerializeAsAny[AIPerfBaseModel | None]
