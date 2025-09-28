# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn


@RequestConverterFactory.register(EndpointType.SOLIDO)
class SolidoRequestConverter(AIPerfLoggerMixin):
    """Request converter for Solido RAG requests."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a Solido RAG request."""

        query_text = " ".join(
            [content for text in turn.texts for content in text.contents]
        )

        payload = {
            "query": query_text,
            "filters": {"family": "Solido", "tool": "SDE"},
            "inference_model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if turn.max_tokens is not None:
            payload["max_completion_tokens"] = turn.max_tokens

        if model_endpoint.endpoint.extra:
            payload.update(dict(model_endpoint.endpoint.extra))

        self.debug(lambda: f"Formatted Solido payload: {payload}")
        return payload
