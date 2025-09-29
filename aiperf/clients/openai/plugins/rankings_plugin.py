# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rankings request converter plugin."""

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn
from aiperf.common.plugins.base import request_converter_plugin


@request_converter_plugin(
    endpoint_types=EndpointType.RANKINGS,
    name="OpenAI Rankings Plugin",
    priority=100,  # High priority for built-in plugins
)
class OpenAIRankingsPlugin(AIPerfLoggerMixin):
    """Request converter plugin for rankings requests.

    Expects texts with specific names:
    - 'query': Single text containing the query to rank against
    - 'passages': Multiple texts containing passages to be ranked
    """

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format payload for a rankings request."""
        if endpoint_type != EndpointType.RANKINGS:
            return None

        if turn.max_tokens:
            self.warning("Max_tokens is provided but is not supported for rankings.")

        query_texts = []
        passage_texts = []

        for text in turn.texts:
            if text.name == "query":
                query_texts.extend(text.contents)
            elif text.name == "passages":
                passage_texts.extend(text.contents)
            else:
                self.warning(
                    f"Ignoring text with name '{text.name}' - rankings expects 'query' and 'passages'"
                )

        if not query_texts:
            raise ValueError(
                "Rankings request requires a text with name 'query'. "
                "Provide a Text object with name='query' containing the search query."
            )

        if len(query_texts) > 1:
            self.warning(
                f"Multiple query texts found, using the first one. Found {len(query_texts)} queries."
            )

        query_text = query_texts[0]

        if not passage_texts:
            self.warning(
                "Rankings request has query but no passages to rank. "
                "Consider adding a Text object with name='passages' containing texts to rank."
            )

        extra = model_endpoint.endpoint.extra or []

        payload = {
            "model": turn.model or model_endpoint.primary_model_name,
            "query": {"text": query_text},
            "passages": [{"text": passage} for passage in passage_texts],
        }

        if extra:
            payload.update(extra)

        return payload
