<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 17: Dataset Loaders

## Overview

Dataset Loaders are the data ingestion layer of AIPerf, responsible for reading files, parsing formats, validating data, and converting to internal representations. This chapter explores the loader architecture, file format support, validation strategies, error handling, and custom loader development.

## Loader Architecture

### Loader Protocol

```python
class DatasetLoaderProtocol(Protocol):
    """Protocol defining the interface for dataset loaders."""

    def load_dataset(self) -> dict[str, list[Any]]:
        """Load dataset from file and return conversations grouped by session_id."""
        ...

    def convert_to_conversations(
        self, data: dict[str, list[Any]]
    ) -> list[Conversation]:
        """Convert loaded data to Conversation objects."""
        ...
```

All loaders implement:
1. `load_dataset()`: Parse file, return data structures
2. `convert_to_conversations()`: Transform to AIPerf's Conversation model

### Factory Registration

```python
@CustomDatasetFactory.register(CustomDatasetType.SINGLE_TURN)
class SingleTurnDatasetLoader(MediaConversionMixin):
    """Loader for single-turn datasets."""
    ...
```

Loaders registered via factory pattern, selected by dataset type enum.

### MediaConversionMixin

Base mixin for handling multi-modal data:

```python
class MediaConversionMixin:
    """Mixin for converting raw data to media objects."""

    def convert_to_media_objects(
        self, data: dict
    ) -> dict[MediaType, list[Media]]:
        """Convert raw data to media objects (Text, Image, Audio)."""
        media = {
            MediaType.TEXT: [],
            MediaType.IMAGE: [],
            MediaType.AUDIO: [],
        }

        # Parse text fields
        if "text" in data:
            media[MediaType.TEXT].append(
                Text(name="text", contents=[data["text"]])
            )
        elif "texts" in data:
            # Handle batched or named text fields
            media[MediaType.TEXT] = self._parse_text_fields(data["texts"])

        # Parse image fields
        if "image" in data:
            media[MediaType.IMAGE].append(
                Image(name="image_url", contents=[data["image"]])
            )
        elif "images" in data:
            media[MediaType.IMAGE] = self._parse_image_fields(data["images"])

        # Parse audio fields
        if "audio" in data:
            media[MediaType.AUDIO].append(
                Audio(name="input_audio", contents=[data["audio"]])
            )
        elif "audios" in data:
            media[MediaType.AUDIO] = self._parse_audio_fields(data["audios"])

        return media
```

Handles:
- Simple fields (`text`, `image`, `audio`)
- Batched fields (`texts`, `images`, `audios`)
- Named fields with multiple content items
- Field name mapping (e.g., `image_url` for OpenAI compatibility)

## File Format Support

### JSONL (JSON Lines)

Most common format - one JSON object per line:

```json
{"text": "Request 1"}
{"text": "Request 2"}
{"text": "Request 3"}
```

**Advantages:**
- Easy to append
- Streaming-friendly
- Human-readable
- Language-agnostic

**Disadvantages:**
- Larger than binary formats
- No schema enforcement

### JSON Array

Single JSON array containing all requests:

```json
[
    {"text": "Request 1"},
    {"text": "Request 2"},
    {"text": "Request 3"}
]
```

**Advantages:**
- Valid JSON
- Easy to validate

**Disadvantages:**
- Must load entire file
- Harder to append

### CSV (Limited Support)

Simple CSV for text-only requests:

```csv
text
"Request 1"
"Request 2"
"Request 3"
```

**Advantages:**
- Compact
- Spreadsheet-compatible

**Disadvantages:**
- Limited to text
- Escaping complexity

## Validation

### Pydantic Model Validation

All data validated via Pydantic:

```python
def load_dataset(self) -> dict[str, list[SingleTurn]]:
    """Load and validate single-turn data."""
    data: dict[str, list[SingleTurn]] = defaultdict(list)

    with open(self.filename) as f:
        for line in f:
            if (line := line.strip()) == "":
                continue  # Skip empty lines

            try:
                single_turn_data = SingleTurn.model_validate_json(line)
                session_id = str(uuid.uuid4())
                data[session_id].append(single_turn_data)
            except ValidationError as e:
                # Handle validation error
                self.logger.error(f"Validation error on line: {line}")
                self.logger.error(f"Error: {e}")
                raise
```

Pydantic enforces:
- Required fields present
- Correct types
- Valid ranges
- Custom validators

### SingleTurn Model

```python
class SingleTurn(AIPerfBaseModel):
    """Model for a single turn in a dataset."""

    # Simple fields
    text: str | None = Field(default=None, description="Simple text content")
    image: str | None = Field(default=None, description="Simple image path/URL")
    audio: str | None = Field(default=None, description="Simple audio path/URL")

    # Batched fields
    texts: list[str] | list[NamedContent] | None = Field(
        default=None, description="Batched/named text contents"
    )
    images: list[str] | list[NamedContent] | None = Field(
        default=None, description="Batched/named image contents"
    )
    audios: list[str] | list[NamedContent] | None = Field(
        default=None, description="Batched/named audio contents"
    )

    # Timing fields
    timestamp: int | None = Field(default=None, description="Absolute timestamp (ms)")
    delay: int | None = Field(default=None, description="Relative delay (ms)")

    # Role field
    role: str | None = Field(default=None, description="Role (user/assistant)")

    @model_validator(mode="after")
    def validate_content(self) -> "SingleTurn":
        """Ensure at least one content field is provided."""
        has_content = any([
            self.text is not None,
            self.image is not None,
            self.audio is not None,
            self.texts is not None,
            self.images is not None,
            self.audios is not None,
        ])
        if not has_content:
            raise ValueError("At least one content field must be provided")
        return self
```

Custom validators ensure:
- At least one content field
- Mutually exclusive timestamp/delay
- Valid file paths (if checking enabled)

### File Path Validation

Optional validation of file paths:

```python
def validate_file_paths(self, data: dict[str, list[SingleTurn]]) -> None:
    """Validate that all referenced files exist."""
    for session_id, turns in data.items():
        for turn in turns:
            # Check image paths
            if turn.image and not Path(turn.image).exists():
                raise FileNotFoundError(f"Image not found: {turn.image}")

            # Check audio paths
            if turn.audio and not Path(turn.audio).exists():
                raise FileNotFoundError(f"Audio not found: {turn.audio}")
```

Can be enabled via config:

```yaml
dataset:
  validate_paths: true
```

## Error Handling

### Graceful Degradation

Loaders can skip invalid lines instead of failing:

```python
def load_dataset(self) -> dict[str, list[SingleTurn]]:
    """Load dataset with error handling."""
    data: dict[str, list[SingleTurn]] = defaultdict(list)
    errors = []

    with open(self.filename) as f:
        for line_num, line in enumerate(f, start=1):
            if (line := line.strip()) == "":
                continue

            try:
                single_turn_data = SingleTurn.model_validate_json(line)
                session_id = str(uuid.uuid4())
                data[session_id].append(single_turn_data)
            except ValidationError as e:
                errors.append((line_num, line, str(e)))
                if self.config.strict_validation:
                    raise
                else:
                    self.logger.warning(
                        f"Skipping invalid line {line_num}: {e}"
                    )

    if errors:
        self.logger.warning(
            f"Loaded dataset with {len(errors)} errors. "
            f"Total valid entries: {sum(len(v) for v in data.values())}"
        )

    return data
```

### Error Reporting

Detailed error reporting:

```python
class LoaderError(Exception):
    """Error during dataset loading."""

    def __init__(
        self,
        message: str,
        filename: str,
        line_num: int | None = None,
        line_content: str | None = None,
    ):
        self.message = message
        self.filename = filename
        self.line_num = line_num
        self.line_content = line_content

    def __str__(self) -> str:
        msg = f"Error loading {self.filename}"
        if self.line_num:
            msg += f" at line {self.line_num}"
        msg += f": {self.message}"
        if self.line_content:
            msg += f"\nLine content: {self.line_content}"
        return msg
```

### Retry Logic

For network-based datasets:

```python
async def load_remote_dataset(
    self,
    url: str,
    max_retries: int = 3,
    backoff: float = 1.0,
) -> dict[str, list[SingleTurn]]:
    """Load dataset from remote URL with retry logic."""
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    content = await response.text()
                    return self._parse_content(content)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                raise LoaderError(f"Failed to load dataset after {max_retries} attempts") from e
            await asyncio.sleep(backoff * (2 ** attempt))
```

## Custom Loaders

### Creating a Custom Loader

**Step 1: Define data model:**

```python
class CustomFormat(AIPerfBaseModel):
    """Model for custom format."""

    query: str = Field(..., description="User query")
    context: str | None = Field(default=None, description="Optional context")
    expected_tokens: int | None = Field(default=None, description="Expected output length")
```

**Step 2: Implement loader:**

```python
@CustomDatasetFactory.register(CustomDatasetType.CUSTOM)
class CustomFormatLoader(MediaConversionMixin):
    """Loader for custom format."""

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self) -> dict[str, list[CustomFormat]]:
        """Load custom format data."""
        data: dict[str, list[CustomFormat]] = defaultdict(list)

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue

                custom_data = CustomFormat.model_validate_json(line)
                session_id = str(uuid.uuid4())
                data[session_id].append(custom_data)

        return data

    def convert_to_conversations(
        self, data: dict[str, list[CustomFormat]]
    ) -> list[Conversation]:
        """Convert to conversations."""
        conversations = []
        for session_id, items in data.items():
            conversation = Conversation(session_id=session_id)
            for item in items:
                # Build prompt from query and context
                prompt = item.query
                if item.context:
                    prompt = f"{item.context}\n\n{prompt}"

                conversation.turns.append(
                    Turn(texts=[Text(name="text", contents=[prompt])])
                )
            conversations.append(conversation)
        return conversations
```

**Step 3: Register in factory:**

```python
# Add to CustomDatasetType enum
class CustomDatasetType(CaseInsensitiveStrEnum):
    ...
    CUSTOM = "custom"

# Loader auto-registers via decorator
```

**Step 4: Use in config:**

```yaml
dataset:
  type: custom
  filename: data/custom_dataset.jsonl
```

### ShareGPT Loader Example

Real-world example - ShareGPT format:

```json
{
    "conversations": [
        {"from": "human", "value": "Hello"},
        {"from": "gpt", "value": "Hi there!"},
        {"from": "human", "value": "How are you?"}
    ]
}
```

Loader implementation:

```python
@CustomDatasetFactory.register(CustomDatasetType.SHAREGPT)
class ShareGPTLoader(MediaConversionMixin):
    """Loader for ShareGPT format."""

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self) -> dict[str, list[ShareGPTConversation]]:
        """Load ShareGPT data."""
        data: dict[str, list[ShareGPTConversation]] = defaultdict(list)

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue

                conv = ShareGPTConversation.model_validate_json(line)
                session_id = str(uuid.uuid4())
                data[session_id].append(conv)

        return data

    def convert_to_conversations(
        self, data: dict[str, list[ShareGPTConversation]]
    ) -> list[Conversation]:
        """Convert ShareGPT to conversations."""
        conversations = []
        for session_id, convs in data.items():
            conversation = Conversation(session_id=session_id)

            for conv in convs:
                for msg in conv.conversations:
                    # Only use 'human' messages as prompts
                    if msg.from_role == "human":
                        conversation.turns.append(
                            Turn(
                                texts=[Text(name="text", contents=[msg.value])],
                                role="user",
                            )
                        )

            conversations.append(conversation)
        return conversations
```

## Loader Utilities

### utils.py

Common utilities for loaders:

```python
def sample_positive_normal_integer(mean: float, stddev: float) -> int:
    """Sample a positive integer from a normal distribution."""
    value = int(random.gauss(mean, stddev))
    return max(1, value)  # Ensure positive

def load_jsonl(filename: str) -> Iterator[dict]:
    """Stream JSONL file line by line."""
    with open(filename) as f:
        for line in f:
            if (line := line.strip()) == "":
                continue
            yield json.loads(line)

def chunk_iterator(iterator: Iterator, chunk_size: int) -> Iterator[list]:
    """Chunk an iterator into batches."""
    chunk = []
    for item in iterator:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
```

### Base Loader Class

Reusable base class:

```python
class BaseDatasetLoader(ABC):
    """Base class for dataset loaders."""

    def __init__(
        self,
        filename: str,
        strict_validation: bool = True,
        validate_paths: bool = False,
    ):
        self.filename = filename
        self.strict_validation = strict_validation
        self.validate_paths = validate_paths
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def load_dataset(self) -> dict[str, list[Any]]:
        """Load dataset from file."""
        ...

    @abstractmethod
    def convert_to_conversations(
        self, data: dict[str, list[Any]]
    ) -> list[Conversation]:
        """Convert to conversations."""
        ...

    def load(self) -> list[Conversation]:
        """Load and convert in one call."""
        data = self.load_dataset()
        return self.convert_to_conversations(data)
```

## Performance Optimization

### Streaming Large Datasets

For very large datasets, stream instead of loading entirely:

```python
class StreamingLoader:
    """Loader that streams data instead of loading all at once."""

    def __init__(self, filename: str, chunk_size: int = 1000):
        self.filename = filename
        self.chunk_size = chunk_size

    def stream_conversations(self) -> Iterator[list[Conversation]]:
        """Stream conversations in chunks."""
        chunk = []

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue

                # Parse and convert
                data = SingleTurn.model_validate_json(line)
                conversation = self._convert_to_conversation(data)
                chunk.append(conversation)

                if len(chunk) >= self.chunk_size:
                    yield chunk
                    chunk = []

        if chunk:
            yield chunk
```

### Parallel Loading

Use multiprocessing for large files:

```python
from multiprocessing import Pool

def load_chunk(chunk_lines: list[str]) -> list[Conversation]:
    """Load a chunk of lines."""
    conversations = []
    for line in chunk_lines:
        data = SingleTurn.model_validate_json(line)
        conversation = convert_to_conversation(data)
        conversations.append(conversation)
    return conversations

def parallel_load(filename: str, num_workers: int = 4) -> list[Conversation]:
    """Load dataset in parallel."""
    with open(filename) as f:
        lines = [line.strip() for line in f if line.strip()]

    # Split into chunks
    chunk_size = len(lines) // num_workers
    chunks = [
        lines[i:i + chunk_size]
        for i in range(0, len(lines), chunk_size)
    ]

    # Process chunks in parallel
    with Pool(num_workers) as pool:
        results = pool.map(load_chunk, chunks)

    # Flatten results
    return [conv for chunk_result in results for conv in chunk_result]
```

### Caching

Cache parsed datasets:

```python
class CachedLoader:
    """Loader with caching."""

    def __init__(self, filename: str, cache_dir: str = ".cache"):
        self.filename = filename
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _cache_path(self) -> Path:
        """Get cache file path."""
        # Hash filename + modification time
        mtime = Path(self.filename).stat().st_mtime
        cache_key = hashlib.md5(
            f"{self.filename}:{mtime}".encode()
        ).hexdigest()
        return self.cache_dir / f"{cache_key}.pkl"

    def load(self) -> list[Conversation]:
        """Load with caching."""
        cache_path = self._cache_path()

        if cache_path.exists():
            self.logger.info(f"Loading from cache: {cache_path}")
            with open(cache_path, "rb") as f:
                return pickle.load(f)

        # Load and cache
        self.logger.info(f"Loading from file: {self.filename}")
        conversations = self._load_from_file()

        with open(cache_path, "wb") as f:
            pickle.dump(conversations, f)

        return conversations
```

## Best Practices

### Validation Strategy

**Strict validation during development:**

```yaml
dataset:
  strict_validation: true  # Fail on any error
  validate_paths: true     # Check file paths exist
```

**Lenient validation in production:**

```yaml
dataset:
  strict_validation: false  # Skip invalid entries
  validate_paths: false     # Assume paths valid
```

### File Organization

```
datasets/
├── text-only/
│   ├── prompts.jsonl
│   └── conversations.jsonl
├── multi-modal/
│   ├── vision.jsonl
│   └── audio.jsonl
├── media/
│   ├── images/
│   └── audio/
└── traces/
    └── production_2024.jsonl
```

### Error Logging

```python
def load_dataset(self) -> dict[str, list[SingleTurn]]:
    """Load with detailed error logging."""
    data = defaultdict(list)
    error_log = []

    with open(self.filename) as f:
        for line_num, line in enumerate(f, start=1):
            try:
                item = SingleTurn.model_validate_json(line)
                data[str(uuid.uuid4())].append(item)
            except Exception as e:
                error_log.append({
                    "line": line_num,
                    "error": str(e),
                    "content": line[:100],  # First 100 chars
                })

    if error_log:
        # Write error log
        with open(f"{self.filename}.errors.json", "w") as f:
            json.dump(error_log, f, indent=2)
        self.logger.warning(
            f"Encountered {len(error_log)} errors. See {self.filename}.errors.json"
        )

    return data
```

## Troubleshooting

### Invalid JSON

**Symptoms:** `json.JSONDecodeError`

**Causes:**
- Malformed JSON
- Extra commas
- Unescaped quotes

**Solutions:**

```python
try:
    data = json.loads(line)
except json.JSONDecodeError as e:
    # Try to identify error location
    self.logger.error(f"JSON error at position {e.pos}")
    self.logger.error(f"Line content: {line}")
    # Show context around error
    start = max(0, e.pos - 20)
    end = min(len(line), e.pos + 20)
    self.logger.error(f"Context: ...{line[start:end]}...")
```

### Memory Issues

**Symptoms:** Out of memory

**Causes:**
- Loading entire large file
- Many large media files
- No chunking

**Solutions:**
- Use streaming loaders
- Process in chunks
- Enable caching
- Use generators instead of lists

### Slow Loading

**Symptoms:** Loading takes minutes

**Causes:**
- Large files
- Complex validation
- Serial processing

**Solutions:**
- Use parallel loading
- Disable expensive validation
- Profile to find bottlenecks

```python
import cProfile

profiler = cProfile.Profile()
profiler.enable()

data = loader.load_dataset()

profiler.disable()
profiler.print_stats(sort="cumulative")
```

## Key Takeaways

1. **Loader Protocol**: All loaders implement `load_dataset()` and `convert_to_conversations()`.

2. **Factory Pattern**: Loaders registered via factory, selected by dataset type enum.

3. **Media Conversion Mixin**: Reusable mixin handles multi-modal data parsing.

4. **Pydantic Validation**: All data validated via Pydantic models with custom validators.

5. **Error Handling**: Graceful degradation, detailed error reporting, retry logic for network loads.

6. **Custom Loaders**: Easy to add via custom models, loader implementation, and factory registration.

7. **File Formats**: JSONL preferred for streaming, JSON arrays for small datasets, CSV for simple text-only.

8. **Performance**: Streaming for large datasets, parallel loading, caching for repeated use.

9. **Best Practices**: Strict validation in development, lenient in production; organize datasets by type; detailed error logging.

10. **Troubleshooting**: JSON errors (show context), memory issues (streaming), slow loading (parallelization).

Next: [Chapter 18: Dataset Composers](chapter-18-dataset-composers.md)
