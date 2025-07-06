# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import time
from abc import ABC
from typing import Any

from aiperf.clients.client_interfaces import EndpointType, InferenceClientFactory
from aiperf.clients.http.aiohttp_client import AioHttpClientMixin
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.dataset_models import Turn
from aiperf.common.record_models import (
    ErrorDetails,
    RequestRecord,
)


class OpenAIClientAioHttp(AioHttpClientMixin, ABC):
    """Base inference client for OpenAI based requests."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        super().__init__(model_endpoint)
        self.model_endpoint = model_endpoint
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_headers(self, model_endpoint: ModelEndpointInfo) -> dict[str, str]:
        """Get the headers for the given endpoint."""
        headers = {
            "User-Agent": "aiperf/1.0",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
            if model_endpoint.endpoint.streaming
            else "application/json",
        }
        if model_endpoint.endpoint.api_key:
            headers["Authorization"] = f"Bearer {model_endpoint.endpoint.api_key}"
        if model_endpoint.endpoint.headers:
            headers.update(model_endpoint.endpoint.headers)
        return headers

    def get_url(self, model_endpoint: ModelEndpointInfo) -> str:
        """Get the URL for the given endpoint."""
        url = model_endpoint.url
        if not url.startswith("http"):
            url = f"http://{url}"
        return url

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: dict[str, Any],
    ) -> RequestRecord:
        """Send OpenAI request using aiohttp."""

        # capture start time before request is sent in the case of an error
        start_perf_ns = time.perf_counter_ns()
        try:
            self.logger.debug(
                "Sending OpenAI request to %s, payload: %s", model_endpoint.url, payload
            )

            record = await self.post_request(
                self.get_url(model_endpoint),
                json.dumps(payload),
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
            self.logger.error(
                "Error in OpenAI request: %s %s",
                e.__class__.__name__,
                str(e),
            )

        return record


@InferenceClientFactory.register(EndpointType.OPENAI_CHAT_COMPLETIONS)
class OpenAIChatCompletionClientAioHttp(OpenAIClientAioHttp):
    """Inference client for OpenAI chat completion requests."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        super().__init__(model_endpoint)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a chat completion request."""

        messages = [
            {
                "role": text.role or "user",
                "name": text.name,
                "content": content,
            }
            for text in turn.text
            for content in text.content
            if content
        ]

        payload = {
            "messages": messages,
            "model": model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        self.logger.debug("Formatted payload: %s", payload)
        return payload


@InferenceClientFactory.register(EndpointType.OPENAI_COMPLETIONS)
class OpenAICompletionClientAioHttp(OpenAIClientAioHttp):
    """Inference client for OpenAI completion requests."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        super().__init__(model_endpoint)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a completion request."""

        payload = {
            "prompt": turn.text,
            "model": model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        self.logger.debug("Formatted payload: %s", payload)
        return payload


@InferenceClientFactory.register(EndpointType.OPENAI_EMBEDDINGS)
class OpenAIEmbeddingsClientAioHttp(OpenAIClientAioHttp):
    """Inference client for OpenAI embeddings requests."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        super().__init__(model_endpoint)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for an embeddings request."""

        payload = {
            "input": turn.text,
            "model": model_endpoint.primary_model_name,
            "dimensions": model_endpoint.endpoint.url_params.get("dimensions", 1536)
            if model_endpoint.endpoint.url_params
            else 1536,
            "encoding_format": model_endpoint.endpoint.url_params.get(
                "encoding_format", "float"
            )
            if model_endpoint.endpoint.url_params
            else "float",
            "user": model_endpoint.endpoint.url_params.get("user", "")
            if model_endpoint.endpoint.url_params
            else "",
            "stream": model_endpoint.endpoint.streaming,
        }

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        self.logger.debug("Formatted payload: %s", payload)
        return payload


@InferenceClientFactory.register(EndpointType.OPENAI_RESPONSES)
class OpenAIResponsesClientAioHttp(OpenAIClientAioHttp):
    """Inference client for OpenAI responses requests."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        super().__init__(model_endpoint)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a responses request."""

        payload = {
            "input": turn.text,
            "model": model_endpoint.primary_model_name,
            "max_output_tokens": model_endpoint.endpoint.url_params.get(
                "max_output_tokens", 1000
            )
            if model_endpoint.endpoint.url_params
            else 1000,
            "stream": model_endpoint.endpoint.streaming,
        }

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        self.logger.debug("Formatted payload: %s", payload)
        return payload
