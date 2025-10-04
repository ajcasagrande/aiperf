<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 27: Request Converters

## Navigation
- Previous: [Chapter 26: TCP Optimizations](chapter-26-tcp-optimizations.md)
- Next: [Chapter 28: Response Parsers](chapter-28-response-parsers.md)
- [Table of Contents](README.md)

## Overview

Request converters transform AIPerf's internal Turn representation into endpoint-specific payload formats. They handle the complexities of different API specifications (Chat, Completions, Embeddings), multimodal content (text, images, audio), and provider-specific requirements while maintaining a unified interface.

This chapter explores the request converter architecture, built-in converters, multimodal support, and how to create custom converters.

## Architecture

### Request Converter Pattern

```
Turn (Internal Format)
    ↓
RequestConverter
    ↓
Payload Dict
    ↓
JSON Serialization
    ↓
HTTP Request
```

**Turn**: AIPerf's internal representation of a conversation turn
**RequestConverter**: Endpoint-specific formatting logic
**Payload Dict**: Python dict matching API specification
**JSON**: Serialized for transmission

### Factory Registration

Request converters use factory pattern for endpoint-specific instantiation:

```python
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.enums import EndpointType

@RequestConverterFactory.register(EndpointType.CHAT)
class OpenAIChatCompletionRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI chat completion requests."""
    pass
```

**Benefits**:
- Automatic selection based on endpoint type
- Easy registration of custom converters
- Decoupled converter implementations
- Type-safe factory lookups

## Turn Model

The Turn model represents a single conversation turn:

```python
@dataclass
class Turn:
    """A single turn in a conversation."""

    # Content
    texts: list[TextContent]        # Text messages
    images: list[ImageContent]      # Image data
    audios: list[AudioContent]      # Audio data

    # Metadata
    role: str | None                # Message role (user, assistant, system)
    model: str | None               # Override model name
    max_tokens: int | None          # Token limit
```

### Content Types

**TextContent**:
```python
@dataclass
class TextContent:
    name: str                       # Content identifier
    contents: list[str]             # Text strings
```

**ImageContent**:
```python
@dataclass
class ImageContent:
    name: str                       # Content identifier
    contents: list[str]             # Base64 or URL
```

**AudioContent**:
```python
@dataclass
class AudioContent:
    name: str                       # Content identifier
    contents: list[str]             # Format,base64 pairs
```

## OpenAI Chat Converter

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/openai/openai_chat.py`

```python
@RequestConverterFactory.register(EndpointType.CHAT)
class OpenAIChatCompletionRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI chat completion requests."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a chat completion request."""

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

        self.debug(lambda: f"Formatted payload: {payload}")
        return payload

    def _create_messages(self, turn: Turn) -> list[dict[str, Any]]:
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
```

### Chat Payload Format

**Text-Only (Simple)**:
```python
{
    "messages": [
        {
            "role": "user",
            "name": "user_message",
            "content": "Hello, how are you?"
        }
    ],
    "model": "gpt-4",
    "stream": true
}
```

**Multimodal (Complex)**:
```python
{
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What's in this image?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64,..."
                    }
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": "base64_audio_data",
                        "format": "wav"
                    }
                }
            ]
        }
    ],
    "model": "gpt-4-vision",
    "stream": true
}
```

### Message Role

```python
DEFAULT_ROLE = "user"

message = {
    "role": turn.role or DEFAULT_ROLE,
}
```

**Common Roles**:
- `"user"`: User messages
- `"assistant"`: Assistant responses
- `"system"`: System instructions

### Model Selection

```python
payload = {
    "model": turn.model or model_endpoint.primary_model_name,
}
```

**Priority**:
1. Turn-specific model (if provided)
2. Endpoint's primary model name
3. First model in model_names list

### Token Limit

```python
if turn.max_tokens is not None:
    payload["max_completion_tokens"] = turn.max_tokens
```

**Note**: Uses `max_completion_tokens` (newer OpenAI API) instead of `max_tokens`

### Extra Parameters

```python
if model_endpoint.endpoint.extra:
    payload.update(model_endpoint.endpoint.extra)
```

**Example Configuration**:
```python
endpoint_config = EndpointConfig(
    extra={
        "temperature": 0.7,
        "top_p": 0.9,
        "presence_penalty": 0.1,
    }
)
```

## Multimodal Support

### Text Content

```python
for text in turn.texts:
    for content in text.contents:
        if not content:
            continue
        message_content.append({"type": "text", "text": content})
```

**Example**:
```python
turn = Turn(
    texts=[
        TextContent(name="prompt", contents=["What is AI?"])
    ]
)

# Converts to:
{
    "type": "text",
    "text": "What is AI?"
}
```

### Image Content

```python
for image in turn.images:
    for content in image.contents:
        if not content:
            continue
        message_content.append(
            {"type": "image_url", "image_url": {"url": content}}
        )
```

**Example**:
```python
turn = Turn(
    images=[
        ImageContent(
            name="input_image",
            contents=["data:image/jpeg;base64,/9j/4AAQSkZJRg..."]
        )
    ]
)

# Converts to:
{
    "type": "image_url",
    "image_url": {
        "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
    }
}
```

**Supported Formats**:
- Data URLs: `data:image/jpeg;base64,...`
- HTTP(S) URLs: `https://example.com/image.jpg`

### Audio Content

```python
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
```

**Format**: `"format,base64_data"`

**Example**:
```python
turn = Turn(
    audios=[
        AudioContent(
            name="voice_input",
            contents=["wav,UklGRiQAAABXQVZFZm10..."]
        )
    ]
)

# Converts to:
{
    "type": "input_audio",
    "input_audio": {
        "data": "UklGRiQAAABXQVZFZm10...",
        "format": "wav"
    }
}
```

**Supported Formats**: wav, mp3, flac, etc. (provider-dependent)

## Completions Converter

For older OpenAI completions endpoint:

```python
@RequestConverterFactory.register(EndpointType.COMPLETIONS)
class OpenAICompletionsRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI completions requests."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a completions request."""

        # Concatenate all text content
        prompt = "\n".join(
            content
            for text in turn.texts
            for content in text.contents
            if content
        )

        payload = {
            "prompt": prompt,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if turn.max_tokens is not None:
            payload["max_tokens"] = turn.max_tokens

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        return payload
```

**Key Difference**: Uses `prompt` string instead of `messages` array

**Example**:
```python
{
    "prompt": "Once upon a time",
    "model": "gpt-3.5-turbo-instruct",
    "max_tokens": 50,
    "stream": false
}
```

## Embeddings Converter

```python
@RequestConverterFactory.register(EndpointType.EMBEDDINGS)
class OpenAIEmbeddingsRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI embeddings requests."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for an embeddings request."""

        # Get text to embed
        input_text = turn.texts[0].contents[0] if turn.texts else ""

        payload = {
            "input": input_text,
            "model": turn.model or model_endpoint.primary_model_name,
        }

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        return payload
```

**Example**:
```python
{
    "input": "The quick brown fox jumps over the lazy dog",
    "model": "text-embedding-ada-002"
}
```

**Note**: Embeddings don't support streaming

## Custom Request Converters

### Creating a Custom Converter

```python
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin

@RequestConverterFactory.register(EndpointType.CUSTOM)
class CustomRequestConverter(AIPerfLoggerMixin):
    """Custom request converter for a specific API."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for custom API."""

        # Extract text content
        text_content = "\n".join(
            content
            for text in turn.texts
            for content in text.contents
            if content
        )

        # Create custom payload format
        payload = {
            "query": text_content,
            "model_id": turn.model or model_endpoint.primary_model_name,
            "parameters": {
                "max_length": turn.max_tokens or 100,
                "streaming": model_endpoint.endpoint.streaming,
            }
        }

        # Add custom parameters
        if model_endpoint.endpoint.extra:
            payload["parameters"].update(model_endpoint.endpoint.extra)

        self.debug(lambda: f"Custom payload: {payload}")
        return payload
```

### Registration and Usage

```python
# Register converter (done via decorator)
@RequestConverterFactory.register(EndpointType.CUSTOM)
class CustomRequestConverter:
    pass

# Automatic usage
converter = RequestConverterFactory.get_or_create_instance(EndpointType.CUSTOM)
payload = await converter.format_payload(model_endpoint, turn)
```

## Error Handling

### Validation

```python
async def format_payload(
    self,
    model_endpoint: ModelEndpointInfo,
    turn: Turn,
) -> dict[str, Any]:
    # Validate required content
    if not turn.texts:
        raise ValueError("Turn must contain text content")

    if not turn.texts[0].contents:
        raise ValueError("Text content cannot be empty")

    # Validate audio format
    for audio in turn.audios:
        for content in audio.contents:
            if "," not in content:
                raise ValueError(
                    "Audio content must be in the format 'format,b64_audio'."
                )

    # Format payload
    payload = self._create_payload(turn)

    return payload
```

### Logging

```python
async def format_payload(
    self,
    model_endpoint: ModelEndpointInfo,
    turn: Turn,
) -> dict[str, Any]:
    self.debug(lambda: f"Formatting payload for endpoint: {model_endpoint.url}")

    payload = self._create_payload(turn)

    self.debug(lambda: f"Formatted payload: {payload}")

    return payload
```

## Testing

### Unit Testing

```python
import pytest
from aiperf.clients.openai.openai_chat import OpenAIChatCompletionRequestConverter
from aiperf.common.models import Turn, TextContent

@pytest.mark.asyncio
async def test_format_text_only():
    """Test formatting text-only messages."""
    converter = OpenAIChatCompletionRequestConverter()

    turn = Turn(
        texts=[TextContent(name="user", contents=["Hello!"])],
        role="user",
    )

    model_endpoint = create_test_endpoint(streaming=False)

    payload = await converter.format_payload(model_endpoint, turn)

    assert payload["messages"] == [
        {
            "role": "user",
            "name": "user",
            "content": "Hello!"
        }
    ]
    assert payload["stream"] == False

@pytest.mark.asyncio
async def test_format_multimodal():
    """Test formatting multimodal messages."""
    converter = OpenAIChatCompletionRequestConverter()

    turn = Turn(
        texts=[TextContent(name="query", contents=["What's this?"])],
        images=[ImageContent(name="img", contents=["data:image/jpeg;base64,..."])],
        role="user",
    )

    model_endpoint = create_test_endpoint()

    payload = await converter.format_payload(model_endpoint, turn)

    assert len(payload["messages"]) == 1
    assert len(payload["messages"][0]["content"]) == 2
    assert payload["messages"][0]["content"][0]["type"] == "text"
    assert payload["messages"][0]["content"][1]["type"] == "image_url"
```

## Performance Considerations

### Async Format

```python
async def format_payload(
    self,
    model_endpoint: ModelEndpointInfo,
    turn: Turn,
) -> dict[str, Any]:
    # Async signature allows for future async operations
    # (e.g., loading images, preprocessing)
    payload = self._create_payload(turn)
    return payload
```

**Why Async**: Enables future enhancements without API changes

### Minimal Allocations

```python
# Efficient: Single list comprehension
message_content = [
    {"type": "text", "text": content}
    for text in turn.texts
    for content in text.contents
    if content
]

# Inefficient: Multiple intermediate lists
temp_list = []
for text in turn.texts:
    for content in text.contents:
        if content:
            temp_list.append({"type": "text", "text": content})
message_content = temp_list
```

### Caching

```python
class CachingRequestConverter:
    def __init__(self):
        self._cache = {}

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        # Create cache key
        cache_key = self._create_cache_key(turn)

        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        # Format payload
        payload = self._create_payload(turn)

        # Store in cache
        self._cache[cache_key] = payload

        return payload
```

**Note**: Only cache if turn objects are immutable and repeated

## Key Takeaways

1. **Factory Pattern**: Automatic selection of converter based on endpoint type

2. **Unified Interface**: All converters implement `format_payload` method

3. **Multimodal Support**: Handle text, images, and audio in single turn

4. **Flexible Configuration**: Extra parameters via endpoint config

5. **Type Safety**: Clear Turn model with typed content

6. **Error Handling**: Validation and logging for debugging

7. **Async Ready**: Async signature enables future enhancements

8. **Extensible**: Easy to add custom converters for new APIs

9. **Testing**: Straightforward unit testing with mock endpoints

10. **Performance**: Efficient implementation with minimal allocations

## What's Next

- **Chapter 28: Response Parsers** - Learn how API responses are extracted and parsed
- **Chapter 24: OpenAI Client** - See how converters integrate with HTTP client

---

**Remember**: Request converters bridge AIPerf's internal representation and external API formats. Master these patterns to support any API specification while maintaining consistent benchmarking semantics.
