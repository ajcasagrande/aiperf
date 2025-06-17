#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import logging
import time
from typing import Any

from aiperf.clients.http.aiohttp_client import AioHttpClientMixin
from aiperf.clients.openai.common import (
    OpenAIBaseRequest,
    OpenAIChatCompletionRequest,
    OpenAIClientConfig,
    OpenAICompletionRequest,
    OpenAIEmbeddingsRequest,
    OpenAIResponsesRequest,
)
from aiperf.common.config.endpoint.endpoint_config import EndPointConfig
from aiperf.common.enums import InferenceClientType
from aiperf.common.exceptions import InvalidPayloadError
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.models.record_models import (
    ErrorDetails,
    RequestRecord,
)

################################################################################
# OpenAI Inference Client
################################################################################

logger = logging.getLogger(__name__)


class ChatCompletionMixin(AioHttpClientMixin):
    """Mixin for chat completion requests."""

    def __init__(self, client_config: OpenAIClientConfig) -> None:
        super().__init__(client_config)

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord:
        """Send chat completion request using aiohttp."""

        record: RequestRecord = RequestRecord(
            start_perf_ns=time.perf_counter_ns(),
            delayed=False,
        )

        try:
            # Prepare request payload
            request_payload = {
                "model": self.client_config.model,
                "messages": payload.messages,
                "max_tokens": self.client_config.max_tokens,
                "stream": payload.stream,
            }

            # Add optional parameters if configured
            if self.client_config.stop:
                request_payload["stop"] = self.client_config.stop

            # Add any additional kwargs from payload
            if payload.kwargs:
                request_payload.update(payload.kwargs)

            # Prepare headers
            headers = {
                "User-Agent": "aiperf/1.0",
                "Content-Type": "application/json",
                "Accept": "text/event-stream" if payload.stream else "application/json",
            }

            if self.client_config.api_key:
                headers["Authorization"] = f"Bearer {self.client_config.api_key}"

            if self.client_config.organization:
                headers["OpenAI-Organization"] = self.client_config.organization

            # Construct full URL
            base_url = (
                f"https://{self.client_config.url}"
                if not self.client_config.url.startswith(("http://", "https://"))
                else self.client_config.url
            )
            url = f"{base_url.rstrip('/')}/{self.client_config.endpoint}"

            record = await self.request(
                url, json.dumps(request_payload), headers, delayed=False
            )

        except Exception as e:
            record.error = ErrorDetails(type=e.__class__.__name__, message=str(e))
            record.end_perf_ns = time.perf_counter_ns()
            logger.error(
                "Error in chat completion request: %s %s",
                e.__class__.__name__,
                str(e),
            )

        return record


@InferenceClientFactory.register(InferenceClientType.OPENAI, override_priority=00)
class OpenAIClientAioHttp(ChatCompletionMixin):
    """A high-performance inference client for communicating with OpenAI based REST APIs using aiohttp.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, client_config: OpenAIClientConfig) -> None:
        super().__init__(client_config)

    async def cleanup(self) -> None:
        """Cleanup the client."""
        await super().cleanup()

    async def format_payload(
        self, endpoint: EndPointConfig, payload: OpenAIBaseRequest | dict[str, Any]
    ) -> OpenAIBaseRequest:
        """Format payload for the given endpoint."""

        if isinstance(payload, dict):
            return self._convert_dict_to_request(endpoint, payload)
        return payload

    def _convert_dict_to_request(
        self, endpoint: EndPointConfig, payload: dict[str, Any]
    ) -> OpenAIBaseRequest:
        """Convert dictionary payload to proper OpenAI request object."""

        if endpoint.type == "v1/chat/completions":
            return OpenAIChatCompletionRequest(
                messages=payload["messages"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )

        elif endpoint.type == "v1/completions":
            return OpenAICompletionRequest(
                prompt=payload["prompt"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )

        elif endpoint.type == "v1/embeddings":
            return OpenAIEmbeddingsRequest(
                input=payload["input"],
                model=self.client_config.model,
                dimensions=payload["dimensions"],
                encoding_format=payload["encoding_format"],
                user=payload["user"],
                kwargs=payload.get("kwargs", {}),
            )

        elif endpoint.type == "v1/responses":
            return OpenAIResponsesRequest(
                input=payload["input"],
                model=self.client_config.model,
                max_output_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )

        else:
            raise ValueError(f"Invalid endpoint: {endpoint}")

    async def send_request(
        self,
        endpoint: EndPointConfig,
        payload: OpenAIBaseRequest,
        delayed: bool = False,
    ) -> RequestRecord:
        """Send request to the specified endpoint with the given payload."""
        record: RequestRecord | None = None
        start_perf_ns = time.perf_counter_ns()

        try:
            if isinstance(payload, OpenAIChatCompletionRequest):
                record = await self.send_chat_completion_request(payload)

            elif isinstance(payload, OpenAICompletionRequest):
                record = await self.send_completion_request(payload)

            elif isinstance(payload, OpenAIEmbeddingsRequest):
                record = await self.send_embeddings_request(payload)

            elif isinstance(payload, OpenAIResponsesRequest):
                record = await self.send_chat_responses_request(payload)

            else:
                raise InvalidPayloadError(f"Invalid payload: {payload}")

        except Exception as e:
            record = RequestRecord(
                start_perf_ns=start_perf_ns,
                delayed=delayed,
                error=ErrorDetails(
                    type=e.__class__.__name__,
                    message=str(e),
                ),
            )

        return record

    async def send_completion_request(
        self, payload: OpenAICompletionRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support completion requests"
        )

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support embeddings requests"
        )

    async def send_chat_responses_request(
        self, payload: OpenAIResponsesRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support chat responses requests"
        )
