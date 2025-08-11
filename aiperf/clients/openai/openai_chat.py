# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn

DEFAULT_ROLE = "user"


@RequestConverterFactory.register(EndpointType.OPENAI_CHAT_COMPLETIONS)
class OpenAIChatCompletionRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI chat completion requests with multi-turn support."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a chat completion request with conversation history."""

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

        self.debug(lambda: f"Formatted payload with {len(messages)} messages")
        return payload

    def _create_messages(self, turn: Turn) -> list[dict[str, Any]]:
        """Create messages list with conversation history support."""

        # Check if this turn contains conversation history
        if (
            turn.texts
            and len(turn.texts) == 1
            and turn.texts[0].name == "conversation_history"
        ):
            # This is a multi-turn request with conversation history
            try:
                conversation_history = json.loads(turn.texts[0].contents[0])
                messages = []

                for msg in conversation_history:
                    # Build message with role and content
                    message = {
                        "role": msg.get("role", DEFAULT_ROLE),
                        "content": msg.get("content", ""),
                    }

                    # Add any additional fields if present
                    if "name" in msg:
                        message["name"] = msg["name"]

                    messages.append(message)

                self.debug(
                    lambda: f"Parsed conversation history with {len(messages)} messages"
                )
                return messages

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                self.warning(f"Failed to parse conversation history: {e}")
                # Fall back to single message format

        # Standard single-turn message format
        message = {
            "role": turn.role or DEFAULT_ROLE,
        }

        if len(turn.texts) == 1 and len(turn.images) == 0 and len(turn.audios) == 0:
            # Simple text-only message
            if turn.texts[0].name and turn.texts[0].name != "conversation_history":
                message["name"] = turn.texts[0].name
            message["content"] = (
                turn.texts[0].contents[0] if turn.texts[0].contents else ""
            )
            return [message]

        # Multi-modal message with content array
        message_content = []

        for text in turn.texts:
            if text.name == "conversation_history":
                continue  # Skip conversation history in multi-modal
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
