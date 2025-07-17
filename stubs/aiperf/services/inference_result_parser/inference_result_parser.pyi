#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio

from aiperf.clients.client_interfaces import (
    ResponseExtractorFactory as ResponseExtractorFactory,
)
from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.comms.base import PullClientProtocol as PullClientProtocol
from aiperf.common.comms.base import PushClientProtocol as PushClientProtocol
from aiperf.common.comms.base import RequestClientProtocol as RequestClientProtocol
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config._user import UserConfig as UserConfig
from aiperf.common.enums import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.factories import ServiceFactory as ServiceFactory
from aiperf.common.hooks import on_configure as on_configure
from aiperf.common.hooks import on_init as on_init
from aiperf.common.messages import CommandMessage as CommandMessage
from aiperf.common.messages import (
    ConversationTurnRequestMessage as ConversationTurnRequestMessage,
)
from aiperf.common.messages import (
    ConversationTurnResponseMessage as ConversationTurnResponseMessage,
)
from aiperf.common.messages import ErrorMessage as ErrorMessage
from aiperf.common.messages import InferenceResultsMessage as InferenceResultsMessage
from aiperf.common.messages import (
    ParsedInferenceResultsMessage as ParsedInferenceResultsMessage,
)
from aiperf.common.record_models import ErrorDetails as ErrorDetails
from aiperf.common.record_models import ParsedResponseRecord as ParsedResponseRecord
from aiperf.common.record_models import RequestRecord as RequestRecord
from aiperf.common.service.base_component_service import (
    BaseComponentService as BaseComponentService,
)
from aiperf.common.tokenizer import Tokenizer as Tokenizer

class InferenceResultParser(BaseComponentService):
    inference_results_client: PullClientProtocol
    records_push_client: PushClientProtocol
    conversation_request_client: RequestClientProtocol
    tokenizers: dict[str, Tokenizer]
    user_config: UserConfig
    tokenizer_lock: asyncio.Lock
    model_endpoint: ModelEndpointInfo
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...
    async def get_tokenizer(self, model: str) -> Tokenizer: ...
    async def process_valid_record(
        self, message: InferenceResultsMessage
    ) -> ParsedResponseRecord: ...
    async def compute_isl(
        self, record: RequestRecord, tokenizer: Tokenizer
    ) -> int | None: ...

def main() -> None: ...
