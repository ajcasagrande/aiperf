# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenAI Chat Completion request converter plugin."""

from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.models import Turn
from aiperf.common.plugins.base import request_converter_plugin

DEFAULT_ROLE = "user"


@request_converter_plugin(
    endpoint_types=EndpointType.CHAT,
    name="OpenAI Chat Completion Plugin",
    priority=100,  # High priority for built-in plugins
)
class OpenAIChatPlugin:
    """Request converter plugin for OpenAI chat completion requests."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format payload for a chat completion request."""
        if endpoint_type != EndpointType.CHAT:
            return None

        messages = self._create_messages(turn)

        payload = {
            "messages": messages,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if turn.max_tokens is not None:
            payload["max_completion_tokens"] = turn.max_tokens

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        return payload

    def _create_messages(self, turn: Turn) -> list[dict[str, Any]]:
        """Create messages list from turn data."""
        message = {
            "role": turn.role or DEFAULT_ROLE,
        }

        if (
            len(turn.texts) == 1
            and len(turn.texts[0].contents) == 1
            and len(turn.images) == 0
            and len(turn.audios) == 0
        ):
            # Hotfix for Dynamo API which does not yet support a list of messages
            message["name"] = turn.texts[0].name
            message["content"] = (
                turn.texts[0].contents[0] if turn.texts[0].contents else ""
            )
            return [message]

        message_content = []

        for text in turn.texts:
            for content in text.contents:
                if not content:
                    continue
                message_content.append({"type": "text", "text": content})

        for image in turn.images:
            for content in image.contents:
                if not content:
                    continue
                message_content.append(
                    {"type": "image_url", "image_url": {"url": content}}
                )

        for audio in turn.audios:
            for content in audio.contents:
                if not content:
                    continue
                if "," not in content:
                    raise ValueError(
                        "Audio content must be in the format 'format,b64_audio'."
                    )
                format, b64_audio = content.split(",", 1)
                message_content.append(
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": b64_audio,
                            "format": format,
                        },
                    }
                )

        message["content"] = message_content
        return [message]
