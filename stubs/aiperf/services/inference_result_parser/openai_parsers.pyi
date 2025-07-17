#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from pydantic import BaseModel as BaseModel

from aiperf.clients.client_interfaces import (
    ResponseExtractorFactory as ResponseExtractorFactory,
)
from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.enums import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum
from aiperf.common.enums import EndpointType as EndpointType
from aiperf.common.models import InferenceServerResponse as InferenceServerResponse
from aiperf.common.models import RequestRecord as RequestRecord
from aiperf.common.models import ResponseData as ResponseData
from aiperf.common.models import SSEMessage as SSEMessage
from aiperf.common.models import TextResponse as TextResponse
from aiperf.common.tokenizer import Tokenizer as Tokenizer
from aiperf.common.utils import load_json_str as load_json_str

logger: Incomplete

class OpenAIObject(CaseInsensitiveStrEnum):
    CHAT_COMPLETION = "chat.completion"
    CHAT_COMPLETION_CHUNK = "chat.completion.chunk"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    RESPONSE = "response"
    @classmethod
    def parse(cls, text: str) -> BaseModel: ...

class OpenAIResponseExtractor:
    model_endpoint: Incomplete
    def __init__(self, model_endpoint: ModelEndpointInfo) -> None: ...
    async def extract_response_data(
        self, record: RequestRecord, tokenizer: Tokenizer | None
    ) -> list[ResponseData]: ...
