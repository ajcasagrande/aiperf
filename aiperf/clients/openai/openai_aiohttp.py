# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from abc import ABC
from typing import Any

import orjson

from aiperf.clients.http.aiohttp_client import AioHttpClientMixin
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import ErrorDetails, RequestRecord


@InferenceClientFactory.register_all(
    EndpointType.OPENAI_CHAT_COMPLETIONS,
    EndpointType.OPENAI_COMPLETIONS,
    EndpointType.OPENAI_EMBEDDINGS,
    EndpointType.OPENAI_RESPONSES,
)
class OpenAIClientAioHttp(AioHttpClientMixin, AIPerfLoggerMixin, ABC):
    """Inference client for OpenAI based requests using aiohttp."""

    def __init__(self, model_endpoint: ModelEndpointInfo, **kwargs) -> None:
        super().__init__(model_endpoint, **kwargs)
        self.model_endpoint = model_endpoint

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: dict[str, Any],
    ) -> RequestRecord:
        """Send OpenAI request using aiohttp."""

        # capture start time before request is sent in the case of an error
        start_perf_ns = time.perf_counter_ns()
        try:
            self.debug(
                lambda: f"Sending OpenAI request to {model_endpoint.url}, payload: {payload}"
            )

            record = await self.post_request(
                self.get_url(model_endpoint),
                orjson.dumps(payload).decode("utf-8"),
                self.get_headers(model_endpoint),
            )
            record.request = payload

        except Exception as e:
            record = RequestRecord(
                request=payload,
                start_perf_ns=start_perf_ns,
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails(type=e.__class__.__name__, message=str(e)),
            )
            self.exception(f"Error in OpenAI request: {e.__class__.__name__} {str(e)}")

        return record
