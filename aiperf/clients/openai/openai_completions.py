# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from aiperf.clients.client_interfaces import RequestConverterFactory
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn


# TODO: Not fully implemented yet.
@RequestConverterFactory.register(EndpointType.OPENAI_COMPLETIONS)
class OpenAICompletionRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI completion requests."""

    def __init__(self) -> None:
        super().__init__()

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a completion request."""

        # TODO: Do we need to support image and audio inputs?
        prompts = [content for text in turn.text for content in text.content if content]

        extra = model_endpoint.endpoint.extra or {}

        payload = {
            "prompt": prompts,
            "model": model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if extra:
            payload.update(extra)

        self.debug(lambda: f"Formatted payload: {payload}")
        return payload
