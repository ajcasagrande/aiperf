# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import time

from aiperf.clients.http.aiohttp_client import AioHttpClientMixin
from aiperf.clients.openai.common import (
    OpenAIBaseRequest,
    OpenAIChatCompletionRequest,
    OpenAIClientConfig,
    OpenAICompletionRequest,
    OpenAIEmbeddingsRequest,
    OpenAIResponsesRequest,
)
from aiperf.common.dataset_models import Turn
from aiperf.common.enums import InferenceClientType
from aiperf.common.exceptions import InvalidPayloadError
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.record_models import (
    ErrorDetails,
    RequestRecord,
)
from aiperf.common.types import ModelEndpointInfo

################################################################################
# OpenAI Inference Client
################################################################################

logger = logging.getLogger(__name__)


class ChatCompletionMixin(AioHttpClientMixin):
    """Mixin for chat completion requests."""

    def __init__(self, client_config: OpenAIClientConfig) -> None:
        super().__init__(client_config)
        self.client_config: OpenAIClientConfig = client_config

    async def send_chat_completion_request(
        self, model_endpoint: ModelEndpointInfo, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord:
        """Send chat completion request using aiohttp."""

        try:
            # Prepare request payload
            request_payload = payload.model_dump()

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
                f"https://{self.client_config.base_url}"
                if not self.client_config.base_url.startswith(("http://", "https://"))
                else self.client_config.base_url
            )
            url = f"{base_url.rstrip('/')}/{self.model_endpoint.endpoint.type}"

            record = await self.post_request(
                url, json.dumps(request_payload), headers, delayed=False
            )
            record.request = request_payload

        except Exception as e:
            record = RequestRecord(
                request=request_payload,
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                delayed=False,
                error=ErrorDetails(type=e.__class__.__name__, message=str(e)),
            )
            logger.error(
                "Error in chat completion request: %s %s",
                e.__class__.__name__,
                str(e),
            )

        return record


@InferenceClientFactory.register(InferenceClientType.OPENAI)
class OpenAIClientAioHttp(ChatCompletionMixin):
    """A high-performance inference client for communicating with OpenAI based REST APIs using aiohttp.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, client_config: OpenAIClientConfig) -> None:
        super().__init__(client_config)
        self.logger = logging.getLogger(__class__.__name__)

    async def close(self) -> None:
        """Close the client."""
        await super().close()

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> OpenAIBaseRequest:
        """Format payload for the given endpoint."""

        if model_endpoint.endpoint.type == "v1/chat/completions":
            messages = [
                {
                    "role": text.role or "user",
                    "name": text.name,
                    "content": text.content,
                }
                for text in turn.text
            ]

            return OpenAIChatCompletionRequest(
                messages=messages,
                model=model_endpoint.models[0].name,
                max_tokens=self.client_config.max_tokens,
                stream=model_endpoint.endpoint.streaming,
                **model_endpoint.endpoint.extra,
            )

        # elif model_endpoint.endpoint.type == "v1/completions":
        #     return OpenAICompletionRequest(
        #         prompt=payload["prompt"],
        #         model=self.client_config.model,
        #         max_tokens=self.client_config.max_tokens,
        #         stream=model_endpoint.endpoint.streaming,
        #         **model_endpoint.endpoint.extra,
        #     )

        # elif model_endpoint.endpoint.type == "v1/embeddings":
        #     return OpenAIEmbeddingsRequest(
        #         input=payload["input"],
        #         model=model_endpoint.models[0].name,
        #         dimensions=payload["dimensions"],
        #         encoding_format=payload["encoding_format"],
        #         user=payload["user"],
        #         **model_endpoint.endpoint.extra,
        #     )

        # elif model_endpoint.endpoint.type == "v1/responses":
        #     return OpenAIResponsesRequest(
        #         input=payload["input"],
        #         model=model_endpoint.models[0].name,
        #         max_output_tokens=model_endpoint.max_output_tokens,
        #         stream=model_endpoint.endpoint.streaming,
        #         **model_endpoint.endpoint.extra,
        #     )

        else:
            raise ValueError(f"Invalid endpoint: {model_endpoint.endpoint.type}")

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: OpenAIBaseRequest,
        delayed: bool = False,
    ) -> RequestRecord:
        """Send request to the specified endpoint with the given payload."""
        record: RequestRecord | None = None
        start_perf_ns = time.perf_counter_ns()

        try:
            if isinstance(payload, OpenAIChatCompletionRequest):
                record = await self.send_chat_completion_request(
                    model_endpoint, payload
                )

            elif isinstance(payload, OpenAICompletionRequest):
                record = await self.send_completion_request(model_endpoint, payload)

            elif isinstance(payload, OpenAIEmbeddingsRequest):
                record = await self.send_embeddings_request(model_endpoint, payload)

            elif isinstance(payload, OpenAIResponsesRequest):
                record = await self.send_chat_responses_request(model_endpoint, payload)

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
        self, model_endpoint: ModelEndpointInfo, payload: OpenAICompletionRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support completion requests"
        )

    async def send_embeddings_request(
        self, model_endpoint: ModelEndpointInfo, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support embeddings requests"
        )

    async def send_chat_responses_request(
        self, model_endpoint: ModelEndpointInfo, payload: OpenAIResponsesRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support chat responses requests"
        )
