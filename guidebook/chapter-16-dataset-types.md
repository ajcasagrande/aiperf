# Chapter 16: Dataset Types

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

AIPerf supports diverse dataset types to accommodate various benchmarking scenarios - from simple single-turn prompts to complex multi-turn conversations, from real-world trace data to synthetic workloads, and from fixed schedules to random distributions. This chapter explores the dataset type architecture, implementation details, use cases, and best practices for each dataset format.

## Dataset Type Architecture

### Dataset Type Hierarchy

```
Dataset Types
├── Single Turn: Independent requests
├── Multi Turn: Conversational sequences
├── Trace: Real-world request traces
├── Random Pool: Random sampling from pool
└── Synthetic: Generated on-the-fly
```

### CustomDatasetType Enum

```python
class CustomDatasetType(CaseInsensitiveStrEnum):
    """Enum for custom dataset types."""

    SINGLE_TURN = "single_turn"
    MULTI_TURN = "multi_turn"
    TRACE = "trace"
    RANDOM_POOL = "random_pool"
    SHAREGPT = "sharegpt"
    MOONCAKE_TRACE = "mooncake_trace"
```

Each type registered via factory pattern:

```python
@CustomDatasetFactory.register(CustomDatasetType.SINGLE_TURN)
class SingleTurnDatasetLoader(MediaConversionMixin):
    """Loader for single turn datasets."""
    ...
```

## Single Turn Datasets

### Overview

Single turn datasets contain independent requests without conversational context. Each line represents a complete, self-contained request.

### Format

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/loader/single_turn.py`:

**Simple text-only:**

```json
{"text": "What is deep learning?"}
```

**Multi-modal:**

```json
{"text": "What is in the image?", "image": "/path/to/image.png"}
```

**Batched (client-side batching):**

```json
{"texts": ["Who are you?", "Hello world"], "images": ["/path/1.png", "/path/2.png"]}
```

**Fixed schedule:**

```json
{"timestamp": 0, "text": "What is deep learning?"}
{"timestamp": 1000, "text": "Who are you?"}
{"timestamp": 2000, "text": "What is AI?"}
```

**Time delayed:**

```json
{"delay": 0, "text": "What is deep learning?"}
{"delay": 1234, "text": "Who are you?"}
```

**Full-featured (multi-batch, multi-modal, multi-fielded):**

```json
{
    "texts": [
        {"name": "text_field_A", "contents": ["Hello", "World"]},
        {"name": "text_field_B", "contents": ["Hi there"]}
    ],
    "images": [
        {"name": "image_field_A", "contents": ["/path/1.png", "/path/2.png"]},
        {"name": "image_field_B", "contents": ["/path/3.png"]}
    ]
}
```

### Implementation

```python
@CustomDatasetFactory.register(CustomDatasetType.SINGLE_TURN)
class SingleTurnDatasetLoader(MediaConversionMixin):
    """A dataset loader that loads single turn data from a file.

    The single turn type:
      - supports multi-modal data (text, image, audio)
      - supports client-side batching (batch_size > 1)
      - DOES NOT support multi-turn features (delay, sessions, etc.)
    """

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self) -> dict[str, list[SingleTurn]]:
        """Load single-turn data from a JSONL file."""
        data: dict[str, list[SingleTurn]] = defaultdict(list)

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue  # Skip empty lines

                single_turn_data = SingleTurn.model_validate_json(line)
                session_id = str(uuid.uuid4())  # Each turn gets unique session
                data[session_id].append(single_turn_data)

        return data

    def convert_to_conversations(
        self, data: dict[str, list[SingleTurn]]
    ) -> list[Conversation]:
        """Convert single turn data to conversation objects."""
        conversations = []
        for session_id, single_turns in data.items():
            conversation = Conversation(session_id=session_id)
            for single_turn in single_turns:
                media = self.convert_to_media_objects(single_turn)
                conversation.turns.append(
                    Turn(
                        texts=media[MediaType.TEXT],
                        images=media[MediaType.IMAGE],
                        audios=media[MediaType.AUDIO],
                        timestamp=single_turn.timestamp,
                        delay=single_turn.delay,
                        role=single_turn.role,
                    )
                )
            conversations.append(conversation)
        return conversations
```

**Key Points:**

- Each turn becomes a single-turn conversation (unique session_id)
- Supports all media types (text, image, audio)
- `timestamp` and `delay` supported for scheduling
- `MediaConversionMixin` handles media parsing

### Use Cases

**1. Simple Prompt Benchmarks:**

```json
{"text": "Translate 'hello' to French"}
{"text": "What is 2+2?"}
{"text": "Explain quantum computing"}
```

**2. Multi-Modal Benchmarks:**

```json
{"text": "Describe this image", "image": "images/scene1.jpg"}
{"text": "What's in the picture?", "image": "images/scene2.jpg"}
```

**3. Fixed Rate Testing:**

```json
{"timestamp": 0, "text": "Request at t=0"}
{"timestamp": 1000, "text": "Request at t=1000ms"}
{"timestamp": 2000, "text": "Request at t=2000ms"}
```

**4. Delayed Sequences:**

```json
{"delay": 0, "text": "Immediate"}
{"delay": 500, "text": "500ms later"}
{"delay": 1000, "text": "1000ms later"}
```

## Multi Turn Datasets

### Overview

Multi turn datasets contain conversational sequences where each turn builds on previous context. Essential for testing conversational AI systems.

### Format

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/loader/multi_turn.py`:

**Simple version:**

```json
{
    "session_id": "session_123",
    "turns": [
        {"text": "Hello", "image": "url", "delay": 0},
        {"text": "Hi there", "delay": 1000}
    ]
}
```

**Batched version:**

```json
{
    "session_id": "session_123",
    "turns": [
        {"texts": ["Who are you?", "Hello world"], "images": ["/path/1.png", "/path/2.png"]},
        {"texts": ["What is in the image?", "What is AI?"], "images": ["/path/3.png", "/path/4.png"]}
    ]
}
```

**Fixed schedule version:**

```json
{
    "session_id": "session_123",
    "turns": [
        {"timestamp": 0, "text": "What is deep learning?"},
        {"timestamp": 1000, "text": "Who are you?"}
    ]
}
```

**Full-featured version:**

```json
{
    "session_id": "session_123",
    "turns": [
        {
            "timestamp": 1234,
            "texts": [
                {"name": "text_field_a", "contents": ["hello", "world"]},
                {"name": "text_field_b", "contents": ["hi there"]}
            ],
            "images": [
                {"name": "image_field_a", "contents": ["/path/1.png", "/path/2.png"]},
                {"name": "image_field_b", "contents": ["/path/3.png"]}
            ]
        }
    ]
}
```

### Implementation

```python
@CustomDatasetFactory.register(CustomDatasetType.MULTI_TURN)
class MultiTurnDatasetLoader(MediaConversionMixin):
    """A dataset loader that loads multi-turn data from a file.

    The multi-turn type:
      - supports multi-modal data (text, image, audio)
      - supports multi-turn features (delay, sessions, etc.)
      - supports client-side batching (batch_size > 1)

    NOTE: If the user specifies multiple multi-turn entries with same session ID,
    the loader will group them together. If timestamps are specified, they will
    be sorted in ascending order later in the timing manager.
    """

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self) -> dict[str, list[MultiTurn]]:
        """Load multi-turn data from a JSONL file."""
        data: dict[str, list[MultiTurn]] = defaultdict(list)

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue  # Skip empty lines

                multi_turn_data = MultiTurn.model_validate_json(line)
                session_id = multi_turn_data.session_id or str(uuid.uuid4())
                data[session_id].append(multi_turn_data)

        return data

    def convert_to_conversations(
        self, data: dict[str, list[MultiTurn]]
    ) -> list[Conversation]:
        """Convert multi-turn data to conversation objects."""
        conversations = []
        for session_id, multi_turns in data.items():
            conversation = Conversation(session_id=session_id)

            # Process all MultiTurn objects for this session
            for multi_turn in multi_turns:
                for single_turn in multi_turn.turns:
                    media = self.convert_to_media_objects(single_turn)
                    conversation.turns.append(
                        Turn(
                            texts=media[MediaType.TEXT],
                            images=media[MediaType.IMAGE],
                            audios=media[MediaType.AUDIO],
                            timestamp=single_turn.timestamp,
                            delay=single_turn.delay,
                            role=single_turn.role,
                        )
                    )
            conversations.append(conversation)
        return conversations
```

**Key Points:**

- Turns grouped by `session_id`
- Multiple entries with same `session_id` are merged
- Turns sorted by `timestamp` if specified
- Supports conversational context across turns

### Use Cases

**1. Conversational Benchmarks:**

```json
{
    "session_id": "conv_1",
    "turns": [
        {"text": "Hello, who are you?"},
        {"text": "What can you do?"},
        {"text": "Tell me more about that"}
    ]
}
```

**2. Multi-Modal Conversations:**

```json
{
    "session_id": "conv_2",
    "turns": [
        {"text": "Here's an image", "image": "image1.jpg"},
        {"text": "What do you see?"},
        {"text": "Can you describe it in detail?"}
    ]
}
```

**3. Delayed Conversations:**

```json
{
    "session_id": "conv_3",
    "turns": [
        {"delay": 0, "text": "Start conversation"},
        {"delay": 5000, "text": "Follow up after 5 seconds"},
        {"delay": 2000, "text": "Final question after 2 more seconds"}
    ]
}
```

## Trace Datasets

### Overview

Trace datasets replay real-world request patterns, preserving timing, concurrency, and distribution characteristics. Essential for realistic performance testing.

### Format

**Mooncake Trace Format:**

```json
{"timestamp": 0, "num_prompts": 50, "num_completions": 100}
{"timestamp": 1000, "num_prompts": 45, "num_completions": 95}
{"timestamp": 2000, "num_prompts": 52, "num_completions": 105}
```

Each line specifies:
- `timestamp`: Milliseconds from start
- `num_prompts`: Input tokens for this request
- `num_completions`: Output tokens for this request

### Implementation

```python
@CustomDatasetFactory.register(CustomDatasetType.MOONCAKE_TRACE)
class MooncakeTraceLoader(MediaConversionMixin):
    """Loader for Mooncake trace format.

    Mooncake traces contain timestamp, num_prompts, and num_completions for each request.
    """

    def __init__(self, filename: str, tokenizer: Tokenizer):
        self.filename = filename
        self.tokenizer = tokenizer
        self.prompt_generator = PromptGenerator(
            config=PromptConfig(),
            tokenizer=tokenizer,
        )

    def load_dataset(self) -> dict[str, list[TraceData]]:
        """Load trace data from file."""
        data: dict[str, list[TraceData]] = defaultdict(list)

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue

                trace_data = TraceData.model_validate_json(line)
                session_id = str(uuid.uuid4())  # Each trace entry = unique session
                data[session_id].append(trace_data)

        return data

    def convert_to_conversations(
        self, data: dict[str, list[TraceData]]
    ) -> list[Conversation]:
        """Convert trace data to conversations with generated prompts."""
        conversations = []
        for session_id, trace_list in data.items():
            conversation = Conversation(session_id=session_id)
            for trace in trace_list:
                # Generate prompt with specified token count
                prompt = self.prompt_generator.generate(
                    mean=trace.num_prompts,
                    stddev=0,  # Exact token count from trace
                )

                conversation.turns.append(
                    Turn(
                        texts=[Text(name="text", contents=[prompt])],
                        timestamp=trace.timestamp,
                    )
                )
            conversations.append(conversation)
        return conversations
```

**Key Points:**

- Preserves exact timing from trace
- Generates synthetic prompts with specified token counts
- Each trace entry becomes a single-turn conversation
- Enables replay of real-world workloads

### Use Cases

**1. Production Replay:**

```json
{"timestamp": 0, "num_prompts": 50, "num_completions": 100}
{"timestamp": 123, "num_prompts": 45, "num_completions": 95}
{"timestamp": 456, "num_prompts": 52, "num_completions": 105}
```

Replay actual production traffic patterns.

**2. Capacity Planning:**

```json
{"timestamp": 0, "num_prompts": 100, "num_completions": 200}
{"timestamp": 100, "num_prompts": 100, "num_completions": 200}
...
```

Test system at higher loads.

**3. Regression Testing:**

```json
{"timestamp": 0, "num_prompts": 50, "num_completions": 100}
{"timestamp": 1000, "num_prompts": 50, "num_completions": 100}
...
```

Consistent workload for comparing versions.

## Random Pool Datasets

### Overview

Random pool datasets contain a pool of requests that are sampled randomly during execution. Useful for testing with varied but repeatable workloads.

### Format

Standard JSONL with mix of requests:

```json
{"text": "Request 1"}
{"text": "Request 2"}
{"text": "Request 3"}
{"text": "Request 4"}
{"text": "Request 5"}
```

During execution, requests are randomly selected from this pool (with or without replacement).

### Implementation

```python
@CustomDatasetFactory.register(CustomDatasetType.RANDOM_POOL)
class RandomPoolLoader(MediaConversionMixin):
    """Loader for random pool datasets.

    Loads a pool of requests that will be randomly sampled during execution.
    """

    def __init__(self, filename: str, pool_size: int, replacement: bool = True):
        self.filename = filename
        self.pool_size = pool_size
        self.replacement = replacement  # Sample with replacement?

    def load_dataset(self) -> dict[str, list[PoolItem]]:
        """Load pool data from file."""
        pool_items = []

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue

                item = PoolItem.model_validate_json(line)
                pool_items.append(item)

        # Create conversations by sampling from pool
        data: dict[str, list[PoolItem]] = {}
        for i in range(self.pool_size):
            session_id = str(uuid.uuid4())
            if self.replacement:
                sampled = random.choice(pool_items)
            else:
                sampled = pool_items[i % len(pool_items)]
            data[session_id] = [sampled]

        return data
```

**Key Points:**

- Pool loaded once at startup
- Requests sampled randomly during execution
- With replacement: Same request can appear multiple times
- Without replacement: Each request used at most once (cycling if needed)

### Use Cases

**1. Varied Workload:**

```json
{"text": "Short query"}
{"text": "Medium length query with more details"}
{"text": "Very long query with extensive context and multiple questions"}
```

Random distribution of request lengths.

**2. Multi-Modal Mix:**

```json
{"text": "Text only"}
{"text": "With image", "image": "image1.jpg"}
{"text": "With audio", "audio": "audio1.wav"}
```

Random mix of modalities.

**3. Topic Distribution:**

```json
{"text": "Math question: What is 2+2?"}
{"text": "Science question: What is photosynthesis?"}
{"text": "History question: Who was Napoleon?"}
```

Random topic sampling.

## Synthetic Datasets

### Overview

Synthetic datasets are generated on-the-fly based on configuration, without pre-existing data files. Ideal for stress testing and parameter sweeps.

### Configuration

```yaml
input:
  conversation:
    num: 100  # Number of conversations
    turn:
      mean: 3  # Average turns per conversation
      stddev: 1
      delay:
        mean: 1000  # Average delay between turns (ms)
        stddev: 200
        ratio: 1.0
  prompt:
    input_tokens:
      mean: 100  # Average input tokens
      stddev: 20
    batch_size: 1
  image:
    width:
      mean: 512
      stddev: 50
    height:
      mean: 512
      stddev: 50
    batch_size: 1
  audio:
    length:
      mean: 5  # Seconds
      stddev: 1
    batch_size: 1
```

### Implementation (Simplified)

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/composer/synthetic.py`:

```python
@ComposerFactory.register(ComposerType.SYNTHETIC)
class SyntheticDatasetComposer(BaseDatasetComposer):
    """Composer for generating synthetic datasets."""

    def create_dataset(self) -> list[Conversation]:
        """Create a synthetic conversation dataset."""
        conversations = []
        for _ in range(self.config.input.conversation.num):
            conversation = Conversation(session_id=str(uuid.uuid4()))

            num_turns = utils.sample_positive_normal_integer(
                self.config.input.conversation.turn.mean,
                self.config.input.conversation.turn.stddev,
            )

            for turn_idx in range(num_turns):
                turn = self._create_turn(is_first=(turn_idx == 0))
                conversation.turns.append(turn)
            conversations.append(conversation)
        return conversations

    def _create_turn(self, is_first: bool) -> Turn:
        """Create a turn with synthetic payloads."""
        turn = Turn()

        if self.include_prompt:
            turn.texts.append(self._generate_text_payloads(is_first))
        if self.include_image:
            turn.images.append(self._generate_image_payloads())
        if self.include_audio:
            turn.audios.append(self._generate_audio_payloads())

        if not is_first:
            delay = utils.sample_positive_normal_integer(
                self.config.input.conversation.turn.delay.mean,
                self.config.input.conversation.turn.delay.stddev,
            )
            turn.delay = delay * self.config.input.conversation.turn.delay.ratio

        return turn

    def _generate_text_payloads(self, is_first: bool) -> Text:
        """Generate synthetic text payloads."""
        text = Text(name="text")
        for _ in range(self.config.input.prompt.batch_size):
            prompt = self.prompt_generator.generate(
                mean=self.config.input.prompt.input_tokens.mean,
                stddev=self.config.input.prompt.input_tokens.stddev,
            )
            text.contents.append(prompt)
        return text
```

**Key Features:**

- **Parametric generation**: All parameters configurable
- **Normal distributions**: Mean/stddev for realistic variation
- **Multi-modal**: Text, image, audio generation
- **Conversational**: Multi-turn with delays
- **No files**: Generated on-the-fly

### Use Cases

**1. Stress Testing:**

```yaml
conversation:
  num: 10000  # Large number of conversations
  turn:
    mean: 1  # Single turn
prompt:
  input_tokens:
    mean: 1000  # Long prompts
    stddev: 0  # Fixed length
```

**2. Parameter Sweeps:**

```yaml
# Test different input lengths
prompt:
  input_tokens:
    mean: [50, 100, 500, 1000, 2000]
```

**3. Multi-Modal Benchmarks:**

```yaml
prompt:
  input_tokens:
    mean: 100
image:
  width:
    mean: 512
  height:
    mean: 512
audio:
  length:
    mean: 5
```

## Dataset Comparison

| Feature | Single Turn | Multi Turn | Trace | Random Pool | Synthetic |
|---------|------------|------------|-------|-------------|-----------|
| File Required | Yes | Yes | Yes | Yes | No |
| Conversational | No | Yes | No | No | Yes |
| Fixed Timing | Optional | Optional | Yes | No | No |
| Multi-Modal | Yes | Yes | No | Yes | Yes |
| Repeatable | Yes | Yes | Yes | Yes | Configurable |
| Realistic | Depends | Depends | Very High | Depends | Low |
| Flexibility | Medium | High | Low | Medium | Very High |

## Best Practices

### Choosing Dataset Type

**Use Single Turn when:**
- Testing independent requests
- No conversational context needed
- Simple prompt benchmarking

**Use Multi Turn when:**
- Testing conversational AI
- Context across turns matters
- Multi-turn latency important

**Use Trace when:**
- Replaying production workloads
- Realistic timing distribution crucial
- Capacity planning

**Use Random Pool when:**
- Need variety without full randomness
- Testing with real prompts
- Reproducibility important

**Use Synthetic when:**
- No existing dataset
- Need parametric control
- Stress testing with extreme parameters

### Dataset Size Considerations

**Small datasets (<1000 requests):**
- Quick iteration during development
- May not reveal performance issues
- Statistical significance limited

**Medium datasets (1000-10000 requests):**
- Balance between speed and coverage
- Good for most benchmarks
- Sufficient statistical power

**Large datasets (>10000 requests):**
- Long-running benchmarks
- High statistical confidence
- May require batching/streaming

### Multi-Modal Considerations

**Image benchmarks:**
- Use consistent image sizes
- Consider compression format (JPEG vs PNG)
- Balance size vs quality

**Audio benchmarks:**
- Specify duration and sample rate
- Use appropriate codec
- Consider streaming vs complete upload

**Mixed modality:**
- Test text-only, image-only, audio-only, and combinations
- Vary modality distribution
- Monitor per-modality metrics

## Troubleshooting

### Dataset Loading Errors

**Symptoms:** `ValidationError` or `FileNotFoundError`

**Causes:**
1. Invalid JSON format
2. Missing required fields
3. File path incorrect

**Solutions:**

```python
try:
    dataset = loader.load_dataset()
except ValidationError as e:
    print(f"Invalid dataset format: {e}")
    # Check specific validation errors
except FileNotFoundError:
    print(f"Dataset file not found: {loader.filename}")
```

### Large Dataset Memory Issues

**Symptoms:** Out of memory errors

**Causes:**
1. Entire dataset loaded into memory
2. Large media files (images/audio)
3. Too many conversations

**Solutions:**

```python
# Stream dataset instead of loading all at once
def stream_dataset(filename: str):
    with open(filename) as f:
        for line in f:
            yield process_line(line)

# Or use chunking
def load_dataset_chunked(filename: str, chunk_size: int = 1000):
    chunks = []
    with open(filename) as f:
        for i, line in enumerate(f):
            chunks.append(process_line(line))
            if (i + 1) % chunk_size == 0:
                yield chunks
                chunks = []
    if chunks:
        yield chunks
```

### Timing Issues

**Symptoms:** Requests not sent at expected times

**Causes:**
1. Timestamps in milliseconds vs nanoseconds
2. Relative vs absolute timestamps
3. Delays not cumulative

**Solutions:**

```python
# Always use nanoseconds internally
timestamp_ns = timestamp_ms * 1_000_000

# For relative timestamps, accumulate
cumulative_timestamp = 0
for turn in turns:
    cumulative_timestamp += turn.delay
    turn.absolute_timestamp = start_time + cumulative_timestamp
```

## Key Takeaways

1. **Five Dataset Types**: Single turn (independent), multi turn (conversational), trace (replay), random pool (varied), synthetic (generated).

2. **Multi-Modal Support**: All types except trace support text, image, and audio modalities.

3. **Timing Control**: Datasets can specify fixed timestamps or relative delays for precise scheduling.

4. **Conversational Context**: Multi turn datasets preserve session_id across turns for context.

5. **Synthetic Flexibility**: Synthetic datasets provide parametric control without pre-existing files.

6. **Trace Realism**: Trace datasets replay real-world patterns for realistic testing.

7. **Random Pool Variety**: Random pool combines variety with repeatability.

8. **Factory Pattern**: All loaders registered via factory for extensibility.

9. **Media Conversion**: `MediaConversionMixin` handles multi-modal data parsing.

10. **Best Practices**: Choose dataset type based on testing goals; consider size, multi-modal needs, and timing requirements.

Next: [Chapter 17: Dataset Loaders](chapter-17-dataset-loaders.md)
