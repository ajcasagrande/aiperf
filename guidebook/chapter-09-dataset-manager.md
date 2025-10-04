<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 9: Dataset Manager

## Table of Contents
- [Dataset Manager Architecture](#dataset-manager-architecture)
- [Data Serving Patterns](#data-serving-patterns)
- [Request Handling](#request-handling)
- [Conversation Management](#conversation-management)
- [Dataset Types](#dataset-types)
- [Implementation Details](#implementation-details)
- [Key Takeaways](#key-takeaways)

## Dataset Manager Architecture

The Dataset Manager (`/home/anthony/nvidia/projects/aiperf/aiperf/dataset/dataset_manager.py`) is responsible for loading, managing, and serving conversation data to workers.

### Primary Responsibilities

1. **Dataset Loading**: Load data from various sources
2. **Data Generation**: Generate synthetic conversations
3. **Data Serving**: Respond to worker data requests
4. **Tokenization**: Count tokens for synthetic generation
5. **Trace Replay**: Support deterministic workload replay

### Initialization

```python
@ServiceFactory.register(ServiceType.DATASET_MANAGER)
class DatasetManager(ReplyClientMixin, BaseComponentService):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            reply_client_address=CommAddress.DATASET_MANAGER_PROXY_BACKEND,
            reply_client_bind=False,
        )

        self.tokenizer: Tokenizer | None = None
        self.dataset: dict[str, Conversation] = {}
        self._session_ids_cache: list[str] = []
        self._conversation_query_random = random.Random(
            self.user_config.input.random_seed
        )
        self.dataset_configured = asyncio.Event()
        self._sequential_iterator_index = 0
        self._use_sequential_iteration = False
```

## Data Serving Patterns

### Request-Reply Pattern

Dataset Manager uses DEALER/ROUTER for request-reply:

```
Worker                Dataset Manager
  │                         │
  │ ConversationRequest     │
  ├────────────────────────→│
  │                         │
  │                         │ Lookup/Select Conversation
  │                         │
  │ ConversationResponse    │
  │←────────────────────────┤
  │                         │
```

### Conversation Request Handler

```python
@on_request(MessageType.CONVERSATION_REQUEST)
async def _handle_conversation_request(
    self, message: ConversationRequestMessage
) -> ConversationResponseMessage:
    """Handle a conversation request."""
    await self._wait_for_dataset_configuration()

    if not self.dataset:
        raise self._service_error("Dataset is empty")

    if message.conversation_id is None:
        # Return random/sequential conversation
        return self._return_any_conversation(
            request_id=message.request_id,
        )
    else:
        # Return specific conversation
        return self._return_conversation_by_id(
            request_id=message.request_id,
            conversation_id=message.conversation_id,
        )
```

## Request Handling

### Random Selection

```python
def _return_any_conversation(
    self, request_id: str | None
) -> ConversationResponseMessage:
    """Return any conversation from the dataset."""

    if self._use_sequential_iteration:
        # Sequential iteration for trace replay
        if self._sequential_iterator_index >= len(self._session_ids_cache):
            self._sequential_iterator_index = 0

        session_id = self._session_ids_cache[self._sequential_iterator_index]
        self._sequential_iterator_index += 1
        conversation = self.dataset[session_id]

    else:
        # Random selection (default)
        session_id = self._conversation_query_random.choice(
            self._session_ids_cache
        )
        conversation = self.dataset[session_id]

    return ConversationResponseMessage(
        service_id=self.service_id,
        request_id=request_id,
        conversation=conversation,
    )
```

### Specific Conversation Lookup

```python
def _return_conversation_by_id(
    self, request_id: str | None, conversation_id: str
) -> ConversationResponseMessage:
    """Return a conversation if it exists."""

    if conversation_id not in self.dataset:
        raise self._service_error(
            f"Conversation {conversation_id} not found in dataset."
        )

    conversation = self.dataset[conversation_id]

    return ConversationResponseMessage(
        service_id=self.service_id,
        request_id=request_id,
        conversation=conversation,
    )
```

## Conversation Management

### Conversation Structure

```python
class Conversation:
    session_id: str                # Unique conversation ID
    turns: list[Turn]              # List of turns
    metadata: dict[str, Any] = {}  # Additional metadata

class Turn:
    role: str                      # "user" or "assistant"
    texts: list[Text]              # Text content
    images: list[Image] = []       # Image content
    audios: list[Audio] = []       # Audio content
    model: str | None = None       # Model to use
    timestamp: int | None = None   # For trace replay
```

### Dataset Configuration

```python
@on_command(CommandType.PROFILE_CONFIGURE)
async def _profile_configure_command(
    self, message: ProfileConfigureCommand
) -> None:
    """Configure the dataset."""

    # Configure tokenizer
    await self._configure_tokenizer()

    # Configure dataset
    await self._configure_dataset()

    # Generate inputs.json file
    await self._generate_inputs_json_file()
```

### Tokenizer Configuration

```python
async def _configure_tokenizer(self) -> None:
    """Configure the tokenizer."""
    tokenizer_name = self.user_config.tokenizer.name
    if tokenizer_name is None:
        tokenizer_name = self.user_config.endpoint.model_names[0]

    self.tokenizer = Tokenizer.from_pretrained(
        tokenizer_name,
        trust_remote_code=self.user_config.tokenizer.trust_remote_code,
        revision=self.user_config.tokenizer.revision,
    )
```

## Dataset Types

### Synthetic Generation

```python
# In _configure_dataset
composer = ComposerFactory.create_instance(
    ComposerType.SYNTHETIC,
    config=self.user_config,
    tokenizer=self.tokenizer,
)
conversations = composer.create_dataset()
self.dataset = {conv.session_id: conv for conv in conversations}
```

### Public Datasets

```python
# ShareGPT format
loader = ShareGPTLoader(self.user_config, self.tokenizer)
dataset = await loader.load_dataset()
conversations = await loader.convert_to_conversations(dataset)
self.dataset = {conv.session_id: conv for conv in conversations}
```

### Custom Datasets

```python
composer = ComposerFactory.create_instance(
    ComposerType.CUSTOM,
    config=self.user_config,
    tokenizer=self.tokenizer,
)
conversations = composer.create_dataset()
self.dataset = {conv.session_id: conv for conv in conversations}
```

### Trace Replay

```python
if (
    self.user_config.input.custom_dataset_type
    == CustomDatasetType.MOONCAKE_TRACE
):
    self._use_sequential_iteration = True  # Sequential, not random
```

## Implementation Details

### Inputs File Generation

```python
async def _generate_inputs_json_file(self) -> None:
    """Generate inputs.json file in artifact directory."""
    file_path = (
        self.user_config.output.artifact_directory
        / OutputDefaults.INPUTS_JSON_FILE
    )

    try:
        model_endpoint = ModelEndpointInfo.from_user_config(self.user_config)
        request_converter = RequestConverterFactory.create_instance(
            model_endpoint.endpoint.type,
        )

        inputs = await self._generate_input_payloads(
            model_endpoint, request_converter
        )

        async with aiofiles.open(file_path, "w") as f:
            await f.write(inputs.model_dump_json(indent=2, exclude_unset=True))

    except Exception as e:
        self.warning(f"Error generating inputs.json file: {e}")
```

### Timing Data Request

For fixed schedule mode:

```python
@on_request(MessageType.DATASET_TIMING_REQUEST)
async def _handle_dataset_timing_request(
    self, message: DatasetTimingRequest
) -> DatasetTimingResponse:
    """Handle a dataset timing request."""

    await self._wait_for_dataset_configuration()

    timing_dataset = []
    for conversation_id, conversation in self.dataset.items():
        for turn in conversation.turns:
            timing_dataset.append((turn.timestamp, conversation_id))

    return DatasetTimingResponse(
        service_id=self.service_id,
        request_id=message.request_id,
        timing_data=timing_dataset,
    )
```

### Dataset Configuration Wait

```python
async def _wait_for_dataset_configuration(self) -> None:
    """Wait for the dataset to be configured if it is not already."""
    if not self.dataset_configured.is_set():
        self.debug("Waiting for dataset to be configured...")
        await asyncio.wait_for(
            self.dataset_configured.wait(),
            timeout=DATASET_CONFIGURATION_TIMEOUT
        )
```

## Key Takeaways

1. **Request-Reply Pattern**: Uses DEALER/ROUTER for efficient request-response with workers.

2. **Multiple Data Sources**: Supports synthetic generation, public datasets, custom datasets, and trace files.

3. **Random or Sequential**: Can serve data randomly (default) or sequentially (trace replay).

4. **Tokenizer Integration**: Uses HuggingFace tokenizers for accurate token counting in synthetic generation.

5. **Conversation-Based**: Data is organized as conversations with multiple turns.

6. **Configuration Event**: Uses asyncio.Event to coordinate dataset configuration.

7. **Reproducible Random**: Uses seeded random number generator for reproducibility.

8. **Inputs File Export**: Generates inputs.json for reproducibility and debugging.

9. **Timing Data Support**: Provides timing data for fixed schedule mode.

10. **Error Handling**: Returns error messages rather than raising exceptions.

Dataset Manager is the data provisioning layer that ensures workers always have appropriate conversation data to execute, supporting both synthetic and realistic workloads.

---

Next: [Chapter 10: Timing Manager](chapter-10-timing-manager.md)
