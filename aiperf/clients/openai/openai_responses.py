# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn


@RequestConverterFactory.register(EndpointType.RESPONSES)
class OpenAIResponsesRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI Responses requests."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a responses request.

        The Responses API uses a different format than Chat Completions:
        - 'input' can be a string or array (not 'messages')
        - Supports 'instructions', 'tools', 'previous_response_id'
        - Uses 'max_output_tokens' instead of 'max_tokens'
        """

        # TODO: Add support for image and audio inputs.
        prompts = [
            content for text in turn.texts for content in text.contents if content
        ]

        # For single prompt, pass as string; for multiple, pass as array
        input_data = prompts[0] if len(prompts) == 1 else prompts

        extra = model_endpoint.endpoint.extra or {}

        payload = {
            "input": input_data,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        # Add optional parameters
        if turn.max_tokens:
            payload["max_output_tokens"] = turn.max_tokens

        # Support common optional parameters from extra config
        optional_params = [
            "temperature",
            "top_p",
            "tools",
            "instructions",
            "previous_response_id",
            "modalities",
        ]
        for param in optional_params:
            if param in extra:
                payload[param] = extra[param]

        # Include any remaining extra parameters
        for key, value in extra.items():
            if key not in payload:
                payload[key] = value

        self.debug(lambda: f"Formatted payload: {payload}")
        return payload
