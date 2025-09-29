# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenAI Embeddings request converter plugin."""

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn
from aiperf.common.plugins.base import request_converter_plugin


@request_converter_plugin(
    endpoint_types=EndpointType.EMBEDDINGS,
    name="OpenAI Embeddings Plugin",
    priority=100,  # High priority for built-in plugins
)
class OpenAIEmbeddingsPlugin(AIPerfLoggerMixin):
    """Request converter plugin for OpenAI embeddings requests."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format payload for an embeddings request."""
        if endpoint_type != EndpointType.EMBEDDINGS:
            return None

        if turn.max_tokens:
            self.error("Max_tokens is provided but is not supported for embeddings.")

        prompts = [
            content for text in turn.texts for content in text.contents if content
        ]

        extra = model_endpoint.endpoint.extra or []

        payload = {
            "model": turn.model or model_endpoint.primary_model_name,
            "input": prompts,
        }

        if extra:
            payload.update(extra)

        return payload
