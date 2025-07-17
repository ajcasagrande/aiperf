#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import typing
from typing import Any

import aiohttp
from _typeshed import Incomplete

from aiperf.clients.http.defaults import AioHttpDefaults as AioHttpDefaults
from aiperf.clients.http.defaults import SocketDefaults as SocketDefaults
from aiperf.clients.model_endpoint_info import ModelEndpointInfo as ModelEndpointInfo
from aiperf.common.aiperf_logger import AIPerfLogger as AIPerfLogger
from aiperf.common.enums import SSEFieldType as SSEFieldType
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.record_models import ErrorDetails as ErrorDetails
from aiperf.common.record_models import RequestRecord as RequestRecord
from aiperf.common.record_models import SSEField as SSEField
from aiperf.common.record_models import SSEMessage as SSEMessage
from aiperf.common.record_models import TextResponse as TextResponse

logger: Incomplete

class AioHttpClientMixin(AIPerfLoggerMixin):
    model_endpoint: Incomplete
    tcp_connector: Incomplete
    timeout: Incomplete
    def __init__(self, model_endpoint: ModelEndpointInfo) -> None: ...
    async def close(self) -> None: ...
    async def post_request(
        self, url: str, payload: str, headers: dict[str, str], **kwargs: Any
    ) -> RequestRecord: ...

class AioHttpSSEStreamReader:
    response: Incomplete
    def __init__(self, response: aiohttp.ClientResponse) -> None: ...
    async def read_complete_stream(self) -> list[SSEMessage]: ...
    async def __aiter__(self) -> typing.AsyncIterator[tuple[str, int]]: ...

def parse_sse_message(raw_message: str, perf_ns: int) -> SSEMessage: ...
def create_tcp_connector(**kwargs) -> aiohttp.TCPConnector: ...
