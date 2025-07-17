#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from _typeshed import Incomplete

from aiperf.clients.client_interfaces import EndpointType as EndpointType
from aiperf.clients.client_interfaces import (
    InferenceClientFactory as InferenceClientFactory,
)
from aiperf.clients.http.aiohttp_client import AioHttpClientMixin as AioHttpClientMixin
from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.record_models import ErrorDetails as ErrorDetails
from aiperf.common.record_models import RequestRecord as RequestRecord

class OpenAIClientAioHttp(AioHttpClientMixin, AIPerfLoggerMixin):
    model_endpoint: Incomplete
    def __init__(self, model_endpoint: ModelEndpointInfo) -> None: ...
    def get_headers(self, model_endpoint: ModelEndpointInfo) -> dict[str, str]: ...
    def get_url(self, model_endpoint: ModelEndpointInfo) -> str: ...
    async def initialize(self) -> None: ...
    async def send_request(
        self, model_endpoint: ModelEndpointInfo, payload: dict[str, Any]
    ) -> RequestRecord: ...
