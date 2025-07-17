#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Generic, Protocol

from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.enums import EndpointType as EndpointType
from aiperf.common.factories import FactoryMixin as FactoryMixin
from aiperf.common.models import RequestRecord as RequestRecord
from aiperf.common.models import ResponseData as ResponseData
from aiperf.common.models import Turn as Turn
from aiperf.common.tokenizer import Tokenizer as Tokenizer
from aiperf.common.types import RequestInputT as RequestInputT
from aiperf.common.types import RequestOutputT as RequestOutputT

class InferenceClientProtocol(Generic[RequestInputT], Protocol):
    def __init__(self, model_endpoint: ModelEndpointInfo) -> None: ...
    async def initialize(self) -> None: ...
    async def send_request(
        self, model_endpoint: ModelEndpointInfo, payload: RequestInputT
    ) -> RequestRecord: ...
    async def close(self) -> None: ...

class InferenceClientFactory(FactoryMixin[EndpointType, InferenceClientProtocol]): ...

class RequestConverterProtocol(Generic[RequestOutputT], Protocol):
    async def format_payload(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> RequestOutputT: ...

class RequestConverterFactory(FactoryMixin[EndpointType, RequestConverterProtocol]): ...

class ResponseExtractorProtocol(Protocol):
    def __init__(self, model_endpoint: ModelEndpointInfo) -> None: ...
    async def extract_response_data(
        self, record: RequestRecord, tokenizer: Tokenizer | None
    ) -> list[ResponseData]: ...

class ResponseExtractorFactory(
    FactoryMixin[EndpointType, ResponseExtractorProtocol]
): ...
