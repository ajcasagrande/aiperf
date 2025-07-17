#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.comms import ReplyClientProtocol as ReplyClientProtocol
from aiperf.common.comms.base import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.enums import ComposerType as ComposerType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import NotificationType as NotificationType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.factories import ComposerFactory as ComposerFactory
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import on_configure as on_configure
from aiperf.common.hooks import on_init as on_init
from aiperf.common.messages import (
    ConversationRequestMessage as ConversationRequestMessage,
)
from aiperf.common.messages import (
    ConversationResponseMessage as ConversationResponseMessage,
)
from aiperf.common.messages import (
    ConversationTurnRequestMessage as ConversationTurnRequestMessage,
)
from aiperf.common.messages import (
    ConversationTurnResponseMessage as ConversationTurnResponseMessage,
)
from aiperf.common.messages import DatasetTimingRequest as DatasetTimingRequest
from aiperf.common.messages import DatasetTimingResponse as DatasetTimingResponse
from aiperf.common.messages import Message as Message
from aiperf.common.messages import NotificationMessage as NotificationMessage
from aiperf.common.models import Conversation as Conversation
from aiperf.common.service.base_component_service import (
    BaseComponentService as BaseComponentService,
)
from aiperf.common.tokenizer import Tokenizer as Tokenizer

DATASET_CONFIGURATION_TIMEOUT: float

class DatasetManager(BaseComponentService):
    user_config: Incomplete
    tokenizer: Tokenizer | None
    dataset: dict[str, Conversation]
    router_reply_client: ReplyClientProtocol
    dataset_configured: Incomplete
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...

def main() -> None: ...
