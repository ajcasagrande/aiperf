<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 18: Dataset Composers

## Overview

Dataset Composers orchestrate the transformation of loaded data into benchmark-ready conversations. While loaders handle file parsing, composers apply business logic - generating synthetic data, applying transformations, managing multimodal content, and preparing conversations for execution. This chapter explores the composer pattern, data transformation pipelines, orchestration strategies, and custom composer development.

## Composer Pattern

### BaseDatasetComposer

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/composer/base.py`:

```python
class BaseDatasetComposer(AIPerfLoggerMixin, ABC):
    """Base class for dataset composers.

    Composers are responsible for creating or transforming datasets based on
    configuration. They coordinate with generators (prompt, image, audio) to
    produce final conversation datasets.
    """

    def __init__(self, config: UserConfig, tokenizer: Tokenizer):
        self.config = config
        self.tokenizer = tokenizer

        # Initialize generators
        self.prompt_generator = PromptGenerator(
            config=config.input.prompt,
            tokenizer=tokenizer,
        )
        self.image_generator = ImageGenerator(
            config=config.input.image,
        )
        self.audio_generator = AudioGenerator(
            config=config.input.audio,
        )

    @abstractmethod
    def create_dataset(self) -> list[Conversation]:
        """Create the dataset. Must be implemented by subclasses."""
        ...

    def _finalize_turn(self, turn: Turn) -> None:
        """Apply final processing to a turn."""
        # Validate turn has content
        if not turn.texts and not turn.images and not turn.audios:
            self.warning("Turn has no content")

        # Apply content limits if configured
        if self.config.input.max_content_per_turn:
            turn.texts = turn.texts[:self.config.input.max_content_per_turn]
            turn.images = turn.images[:self.config.input.max_content_per_turn]
            turn.audios = turn.audios[:self.config.input.max_content_per_turn]
```

**Key Responsibilities:**

1. **Generator Coordination**: Manages prompt, image, and audio generators
2. **Dataset Creation**: Produces final conversation list
3. **Turn Finalization**: Applies limits, validation, transformations
4. **Configuration Application**: Uses UserConfig to guide composition

### ComposerType Enum

```python
class ComposerType(CaseInsensitiveStrEnum):
    """Types of dataset composers."""

    SYNTHETIC = "synthetic"
    CUSTOM = "custom"
    FILE = "file"
```

### Factory Registration

```python
@ComposerFactory.register(ComposerType.SYNTHETIC)
class SyntheticDatasetComposer(BaseDatasetComposer):
    """Composer for synthetic datasets."""
    ...
```

## Synthetic Composer

### Overview

The Synthetic Composer generates datasets on-the-fly based on statistical parameters. No input files required - everything generated from configuration.

### Implementation

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/composer/synthetic.py`:

```python
@ComposerFactory.register(ComposerType.SYNTHETIC)
class SyntheticDatasetComposer(BaseDatasetComposer):
    """Composer for generating synthetic datasets.

    Creates conversations with:
    - Configurable number of conversations and turns
    - Normal distribution sampling for token counts, delays, etc.
    - Multi-modal content (text, image, audio)
    - Realistic turn timing via delays
    """

    def __init__(self, config: UserConfig, tokenizer: Tokenizer):
        super().__init__(config, tokenizer)

        if (
            not self.include_prompt
            and not self.include_image
            and not self.include_audio
        ):
            raise ValueError(
                "All synthetic data are disabled. "
                "Please enable at least one of prompt, image, or audio by "
                "setting the mean to a positive value."
            )

    def create_dataset(self) -> list[Conversation]:
        """Create a synthetic conversation dataset."""
        conversations = []
        for _ in range(self.config.input.conversation.num):
            conversation = Conversation(session_id=str(uuid.uuid4()))

            num_turns = utils.sample_positive_normal_integer(
                self.config.input.conversation.turn.mean,
                self.config.input.conversation.turn.stddev,
            )
            self.logger.debug("Creating conversation with %d turns", num_turns)

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

        self._finalize_turn(turn)
        return turn

    def _generate_text_payloads(self, is_first: bool) -> Text:
        """Generate synthetic text payloads."""
        text = Text(name="text")
        for _ in range(self.config.input.prompt.batch_size):
            prompt = self.prompt_generator.generate(
                mean=self.config.input.prompt.input_tokens.mean,
                stddev=self.config.input.prompt.input_tokens.stddev,
            )

            if self.prefix_prompt_enabled and is_first:
                prefix_prompt = self.prompt_generator.get_random_prefix_prompt()
                prompt = f"{prefix_prompt} {prompt}"

            text.contents.append(prompt)
        return text

    def _generate_image_payloads(self) -> Image:
        """Generate synthetic images."""
        image = Image(name="image_url")
        for _ in range(self.config.input.image.batch_size):
            data = self.image_generator.generate()
            image.contents.append(data)
        return image

    def _generate_audio_payloads(self) -> Audio:
        """Generate synthetic audios."""
        audio = Audio(name="input_audio")
        for _ in range(self.config.input.audio.batch_size):
            data = self.audio_generator.generate()
            audio.contents.append(data)
        return audio

    @property
    def include_prompt(self) -> bool:
        return self.config.input.prompt.input_tokens.mean > 0

    @property
    def include_image(self) -> bool:
        return (
            self.config.input.image.width.mean > 0
            and self.config.input.image.height.mean > 0
        )

    @property
    def include_audio(self) -> bool:
        return self.config.input.audio.length.mean > 0

    @property
    def prefix_prompt_enabled(self) -> bool:
        return self.config.input.prompt.prefix_prompt.pool_size > 0
```

**Key Features:**

- **Normal Distribution Sampling**: Realistic variation in token counts, delays, etc.
- **Multi-Modal**: Generates text, image, and audio content
- **Conversational**: Multi-turn support with inter-turn delays
- **Prefix Prompts**: Optional system prompts for first turn
- **Batch Support**: Client-side batching for all modalities

### Configuration Example

```yaml
input:
  conversation:
    num: 100  # 100 conversations
    turn:
      mean: 3  # Average 3 turns per conversation
      stddev: 1
      delay:
        mean: 1000  # Average 1 second between turns
        stddev: 200
        ratio: 1.0
  prompt:
    input_tokens:
      mean: 100  # Average 100 input tokens
      stddev: 20
    batch_size: 1
    prefix_prompt:
      pool_size: 10  # Generate 10 prefix prompts
      length: 50     # 50 tokens each
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
      mean: 5  # 5 seconds
      stddev: 1
    batch_size: 1
```

## Custom Composer

### Overview

Custom composers apply business logic to loaded datasets - transforming, filtering, augmenting, or restructuring data.

### Implementation

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/composer/custom.py`:

```python
@ComposerFactory.register(ComposerType.CUSTOM)
class CustomDatasetComposer(BaseDatasetComposer):
    """Composer that applies custom transformations to loaded datasets.

    Useful for:
    - Filtering conversations by criteria
    - Augmenting data (e.g., adding synthetic images to text-only data)
    - Applying business logic transformations
    - Sampling subsets for quick testing
    """

    def __init__(
        self,
        config: UserConfig,
        tokenizer: Tokenizer,
        conversations: list[Conversation],
    ):
        super().__init__(config, tokenizer)
        self.base_conversations = conversations

    def create_dataset(self) -> list[Conversation]:
        """Apply transformations to base conversations."""
        conversations = self.base_conversations

        # Apply transformations in sequence
        conversations = self._filter_conversations(conversations)
        conversations = self._augment_conversations(conversations)
        conversations = self._sample_conversations(conversations)

        return conversations

    def _filter_conversations(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Filter conversations based on criteria."""
        if not self.config.input.filter_enabled:
            return conversations

        filtered = []
        for conv in conversations:
            # Example filters
            if self._should_include_conversation(conv):
                filtered.append(conv)

        self.logger.info(
            f"Filtered {len(conversations)} -> {len(filtered)} conversations"
        )
        return filtered

    def _should_include_conversation(self, conv: Conversation) -> bool:
        """Determine if conversation should be included."""
        # Filter by number of turns
        if self.config.input.min_turns and len(conv.turns) < self.config.input.min_turns:
            return False
        if self.config.input.max_turns and len(conv.turns) > self.config.input.max_turns:
            return False

        # Filter by content type
        has_images = any(turn.images for turn in conv.turns)
        if self.config.input.require_images and not has_images:
            return False

        return True

    def _augment_conversations(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Augment conversations with additional content."""
        if not self.config.input.augment_enabled:
            return conversations

        augmented = []
        for conv in conversations:
            # Example augmentations
            if self.config.input.add_synthetic_images:
                conv = self._add_images_to_conversation(conv)
            if self.config.input.normalize_token_counts:
                conv = self._normalize_token_counts(conv)

            augmented.append(conv)

        return augmented

    def _add_images_to_conversation(self, conv: Conversation) -> Conversation:
        """Add synthetic images to text-only turns."""
        for turn in conv.turns:
            if turn.texts and not turn.images:
                # Generate synthetic image
                image_data = self.image_generator.generate()
                turn.images.append(
                    Image(name="image_url", contents=[image_data])
                )
        return conv

    def _normalize_token_counts(self, conv: Conversation) -> Conversation:
        """Adjust prompts to target token count."""
        target = self.config.input.target_token_count
        for turn in conv.turns:
            for text in turn.texts:
                for i, content in enumerate(text.contents):
                    # Tokenize and adjust
                    tokens = self.tokenizer.encode(content)
                    if len(tokens) < target:
                        # Pad with synthetic text
                        padding = self.prompt_generator.generate(
                            mean=target - len(tokens),
                            stddev=0,
                        )
                        text.contents[i] = f"{content} {padding}"
                    elif len(tokens) > target:
                        # Truncate
                        truncated_tokens = tokens[:target]
                        text.contents[i] = self.tokenizer.decode(truncated_tokens)
        return conv

    def _sample_conversations(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Sample a subset of conversations."""
        if not self.config.input.sample_size:
            return conversations

        sample_size = min(self.config.input.sample_size, len(conversations))
        sampled = random.sample(conversations, sample_size)

        self.logger.info(
            f"Sampled {sample_size} from {len(conversations)} conversations"
        )
        return sampled
```

**Transformation Types:**

1. **Filtering**: Remove conversations not meeting criteria
2. **Augmentation**: Add synthetic content (images, audio, text)
3. **Normalization**: Standardize token counts, formats
4. **Sampling**: Select random subset for testing

## Pipeline Orchestration

### Multi-Stage Pipeline

Composers can chain transformations:

```python
class PipelineComposer(BaseDatasetComposer):
    """Composer that applies a pipeline of transformations."""

    def __init__(
        self,
        config: UserConfig,
        tokenizer: Tokenizer,
        conversations: list[Conversation],
    ):
        super().__init__(config, tokenizer)
        self.base_conversations = conversations

        # Define transformation pipeline
        self.pipeline: list[Callable] = [
            self._validate_conversations,
            self._filter_by_criteria,
            self._deduplicate_conversations,
            self._augment_with_synthetic_data,
            self._normalize_formats,
            self._apply_business_rules,
            self._sample_final_dataset,
        ]

    def create_dataset(self) -> list[Conversation]:
        """Execute transformation pipeline."""
        conversations = self.base_conversations

        for i, transform in enumerate(self.pipeline):
            self.logger.info(
                f"Pipeline stage {i+1}/{len(self.pipeline)}: {transform.__name__}"
            )
            conversations = transform(conversations)
            self.logger.info(f"  Result: {len(conversations)} conversations")

        return conversations

    def _validate_conversations(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Validate and remove invalid conversations."""
        valid = []
        for conv in conversations:
            if self._is_valid_conversation(conv):
                valid.append(conv)
            else:
                self.logger.warning(f"Invalid conversation: {conv.session_id}")
        return valid

    def _deduplicate_conversations(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Remove duplicate conversations."""
        seen_hashes = set()
        unique = []

        for conv in conversations:
            # Hash conversation content
            conv_hash = self._hash_conversation(conv)
            if conv_hash not in seen_hashes:
                seen_hashes.add(conv_hash)
                unique.append(conv)

        self.logger.info(
            f"Removed {len(conversations) - len(unique)} duplicates"
        )
        return unique

    def _hash_conversation(self, conv: Conversation) -> str:
        """Generate hash of conversation content."""
        import hashlib

        content = ""
        for turn in conv.turns:
            for text in turn.texts:
                content += "".join(text.contents)

        return hashlib.md5(content.encode()).hexdigest()

    def _apply_business_rules(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Apply domain-specific business rules."""
        # Example: Ensure all conversations have proper formatting
        for conv in conversations:
            # Ensure first turn is from user
            if conv.turns and conv.turns[0].role != "user":
                conv.turns[0].role = "user"

            # Ensure alternating roles
            for i, turn in enumerate(conv.turns):
                expected_role = "user" if i % 2 == 0 else "assistant"
                turn.role = expected_role

        return conversations
```

### Parallel Composition

For large datasets, parallelize composition:

```python
from multiprocessing import Pool

class ParallelComposer(BaseDatasetComposer):
    """Composer with parallel processing."""

    def __init__(
        self,
        config: UserConfig,
        tokenizer: Tokenizer,
        conversations: list[Conversation],
        num_workers: int = 4,
    ):
        super().__init__(config, tokenizer)
        self.base_conversations = conversations
        self.num_workers = num_workers

    def create_dataset(self) -> list[Conversation]:
        """Compose dataset in parallel."""
        # Split conversations into chunks
        chunk_size = len(self.base_conversations) // self.num_workers
        chunks = [
            self.base_conversations[i:i + chunk_size]
            for i in range(0, len(self.base_conversations), chunk_size)
        ]

        # Process chunks in parallel
        with Pool(self.num_workers) as pool:
            results = pool.map(self._process_chunk, chunks)

        # Flatten results
        return [conv for chunk_result in results for conv in chunk_result]

    def _process_chunk(self, conversations: list[Conversation]) -> list[Conversation]:
        """Process a chunk of conversations."""
        processed = []
        for conv in conversations:
            # Apply transformations
            conv = self._augment_conversation(conv)
            processed.append(conv)
        return processed
```

## Data Transformation

### Token Count Normalization

Ensure consistent token counts:

```python
def normalize_token_counts(
    self,
    conversations: list[Conversation],
    target_tokens: int,
    tolerance: float = 0.1,
) -> list[Conversation]:
    """Normalize prompt token counts to target."""
    normalized = []

    for conv in conversations:
        for turn in conv.turns:
            for text in turn.texts:
                for i, content in enumerate(text.contents):
                    current_tokens = len(self.tokenizer.encode(content))
                    diff = abs(current_tokens - target_tokens) / target_tokens

                    if diff > tolerance:
                        # Adjust token count
                        if current_tokens < target_tokens:
                            # Pad
                            padding_tokens = target_tokens - current_tokens
                            padding = self.prompt_generator.generate(
                                mean=padding_tokens,
                                stddev=0,
                            )
                            text.contents[i] = f"{content} {padding}"
                        else:
                            # Truncate
                            tokens = self.tokenizer.encode(content)[:target_tokens]
                            text.contents[i] = self.tokenizer.decode(tokens)

        normalized.append(conv)

    return normalized
```

### Multi-Modal Augmentation

Add synthetic multi-modal content:

```python
def augment_with_images(
    self,
    conversations: list[Conversation],
    probability: float = 0.5,
) -> list[Conversation]:
    """Randomly add images to conversations."""
    for conv in conversations:
        for turn in conv.turns:
            if random.random() < probability and not turn.images:
                # Generate synthetic image
                image_data = self.image_generator.generate()
                turn.images.append(
                    Image(name="image_url", contents=[image_data])
                )
    return conversations

def augment_with_audio(
    self,
    conversations: list[Conversation],
    probability: float = 0.3,
) -> list[Conversation]:
    """Randomly add audio to conversations."""
    for conv in conversations:
        for turn in conv.turns:
            if random.random() < probability and not turn.audios:
                # Generate synthetic audio
                audio_data = self.audio_generator.generate()
                turn.audios.append(
                    Audio(name="input_audio", contents=[audio_data])
                )
    return conversations
```

### Content Filtering

Filter based on content criteria:

```python
def filter_by_content(
    self,
    conversations: list[Conversation],
    min_text_length: int = 10,
    max_text_length: int = 1000,
    require_multimodal: bool = False,
) -> list[Conversation]:
    """Filter conversations by content criteria."""
    filtered = []

    for conv in conversations:
        valid = True

        for turn in conv.turns:
            # Check text length
            for text in turn.texts:
                for content in text.contents:
                    if len(content) < min_text_length or len(content) > max_text_length:
                        valid = False
                        break

            # Check multimodal requirement
            if require_multimodal:
                has_multiple_modalities = sum([
                    bool(turn.texts),
                    bool(turn.images),
                    bool(turn.audios),
                ]) >= 2
                if not has_multiple_modalities:
                    valid = False

        if valid:
            filtered.append(conv)

    return filtered
```

## Custom Composer Development

### Step 1: Define Transformation Logic

```python
class MyCustomComposer(BaseDatasetComposer):
    """Custom composer for specific use case."""

    def create_dataset(self) -> list[Conversation]:
        """Create dataset with custom logic."""
        # Start with loaded or generated conversations
        conversations = self._load_base_data()

        # Apply custom transformations
        conversations = self._apply_custom_transformation(conversations)

        return conversations

    def _apply_custom_transformation(
        self, conversations: list[Conversation]
    ) -> list[Conversation]:
        """Apply domain-specific transformation."""
        # Your custom logic here
        ...
        return conversations
```

### Step 2: Register Composer

```python
# Add to ComposerType enum
class ComposerType(CaseInsensitiveStrEnum):
    ...
    MY_CUSTOM = "my_custom"

# Register composer
@ComposerFactory.register(ComposerType.MY_CUSTOM)
class MyCustomComposer(BaseDatasetComposer):
    ...
```

### Step 3: Use in Configuration

```yaml
dataset:
  composer: my_custom
  # Custom composer parameters
  my_custom:
    transformation_param: value
```

## Best Practices

### Idempotency

Ensure transformations are idempotent:

```python
def _augment_conversation(self, conv: Conversation) -> Conversation:
    """Idempotent augmentation."""
    # Check if already augmented
    if hasattr(conv, "_augmented"):
        return conv

    # Apply augmentation
    # ...

    # Mark as augmented
    conv._augmented = True
    return conv
```

### Logging

Detailed logging of transformations:

```python
def create_dataset(self) -> list[Conversation]:
    """Create dataset with detailed logging."""
    self.logger.info(f"Starting composition with {len(self.base_conversations)} conversations")

    conversations = self.base_conversations

    # Track metrics at each stage
    stages = [
        ("filter", self._filter_conversations),
        ("augment", self._augment_conversations),
        ("sample", self._sample_conversations),
    ]

    for stage_name, stage_func in stages:
        prev_count = len(conversations)
        conversations = stage_func(conversations)
        curr_count = len(conversations)

        self.logger.info(
            f"{stage_name}: {prev_count} -> {curr_count} conversations "
            f"({curr_count - prev_count:+d})"
        )

    self.logger.info(f"Final dataset: {len(conversations)} conversations")
    return conversations
```

### Validation

Validate after each transformation:

```python
def _validate_after_transformation(
    self, conversations: list[Conversation]
) -> None:
    """Validate conversations after transformation."""
    for conv in conversations:
        # Ensure valid structure
        assert conv.session_id, "Missing session_id"
        assert conv.turns, "No turns in conversation"

        for turn in conv.turns:
            # Ensure at least one content type
            assert (
                turn.texts or turn.images or turn.audios
            ), f"Turn has no content: {conv.session_id}"
```

## Troubleshooting

### Memory Issues

**Symptoms:** Out of memory during composition

**Causes:**
- Large datasets
- Multiple copies during transformation
- Generator caching

**Solutions:**

```python
# Process in chunks
def create_dataset(self) -> list[Conversation]:
    """Compose dataset in chunks."""
    chunk_size = 1000
    results = []

    for i in range(0, len(self.base_conversations), chunk_size):
        chunk = self.base_conversations[i:i + chunk_size]
        processed = self._process_chunk(chunk)
        results.extend(processed)

        # Clear caches
        self.prompt_generator.clear_cache()

    return results
```

### Performance Issues

**Symptoms:** Slow composition

**Causes:**
- Expensive transformations
- Serial processing
- Redundant tokenization

**Solutions:**
- Use parallel processing
- Cache tokenization results
- Profile to find bottlenecks

## Key Takeaways

1. **Composer Pattern**: Composers orchestrate dataset creation/transformation, coordinating with generators.

2. **Synthetic Composer**: Generates datasets on-the-fly based on statistical parameters; no input files required.

3. **Custom Composer**: Applies business logic transformations to loaded datasets (filtering, augmentation, normalization).

4. **Pipeline Orchestration**: Chain multiple transformations in sequence with logging at each stage.

5. **Data Transformations**: Token normalization, multi-modal augmentation, content filtering, deduplication.

6. **Parallel Composition**: For large datasets, use multiprocessing to parallelize transformations.

7. **Generator Coordination**: Composers manage prompt, image, and audio generators for synthetic content.

8. **Factory Registration**: Composers registered via factory pattern for extensibility.

9. **Best Practices**: Ensure idempotency, detailed logging, validation after transformations.

10. **Troubleshooting**: Chunk processing for memory issues, parallelization for performance, caching for efficiency.

Next: [Chapter 19: Data Generators](chapter-19-data-generators.md)
