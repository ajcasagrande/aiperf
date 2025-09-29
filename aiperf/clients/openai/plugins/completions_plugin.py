# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenAI Completions request converter plugin."""

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.models import Turn
from aiperf.common.plugins.base import request_converter_plugin


@request_converter_plugin(
    endpoint_types=EndpointType.COMPLETIONS,
    name="OpenAI Completions Plugin",
    priority=100,  # High priority for built-in plugins
)
class OpenAICompletionsPlugin:
    """Request converter plugin for OpenAI completion requests."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format payload for a completion request."""
        if endpoint_type != EndpointType.COMPLETIONS:
            return None

        prompts = [
            content for text in turn.texts for content in text.contents if content
        ]

        extra = model_endpoint.endpoint.extra or []

        payload = {
            "prompt": prompts,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if turn.max_tokens:
            payload["max_tokens"] = turn.max_tokens

        if extra:
            payload.update(extra)

        return payload
