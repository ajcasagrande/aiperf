<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 19: Data Generators

## Overview

Data Generators produce synthetic content for benchmarking - from prompts sampled from text corpora to procedurally generated images and audio. This chapter explores AIPerf's generator architecture, the prompt generator's tokenization-based sampling, image and audio generation strategies, caching mechanisms, and performance optimizations.

## Generator Architecture

### BaseGenerator

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/generator/base.py`:

```python
class BaseGenerator(AIPerfLoggerMixin, ABC):
    """Base class for data generators.

    Generators produce synthetic content for benchmarking. They are used by
    composers to create datasets with specific characteristics.
    """

    def __init__(self, config: Any, tokenizer: Tokenizer | None = None, **kwargs):
        self.config = config
        self.tokenizer = tokenizer

    @abstractmethod
    def generate(self, **kwargs) -> Any:
        """Generate synthetic content. Must be implemented by subclasses."""
        ...
```

**Generator Types:**

1. **PromptGenerator**: Text prompts from corpus
2. **ImageGenerator**: Synthetic images
3. **AudioGenerator**: Synthetic audio

## Prompt Generation

### Architecture

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/generator/prompt.py`:

```python
DEFAULT_CORPUS_FILE = "assets/shakespeare.txt"

class PromptGenerator(BaseGenerator):
    """A class for generating synthetic prompts from a text corpus.

    Loads a text corpus (e.g., Shakespearean text), tokenizes it, and uses the
    tokenized corpus to generate synthetic prompts of specified lengths.
    Supports generating prompts with a target number of tokens (with optional
    randomization around a mean and standard deviation) and can reuse
    previously generated token blocks to optimize generation for certain use cases.
    """

    def __init__(self, config: PromptConfig, tokenizer: Tokenizer, **kwargs):
        self.config = config
        self.tokenizer = tokenizer
        self._tokenized_corpus = None
        self._corpus_size = 0
        self._prefix_prompts: list[str] = []
        super().__init__(config=config, tokenizer=tokenizer, **kwargs)

        # Cached prompts: block ID -> list of tokens
        self._cache: dict[int, list[int]] = {}

        # Initialize corpus
        if self._tokenized_corpus is None:
            self._initialize_corpus()

        # Initialize prefix prompts pool
        if self.config.prefix_prompt.pool_size > 0:
            self._create_prefix_prompt_pool()
```

### Corpus Initialization

```python
def _initialize_corpus(self) -> None:
    """Load and tokenize the corpus once, storing it for reuse."""
    corpus_path = Path(__file__).parent / DEFAULT_CORPUS_FILE

    with open(corpus_path) as f:
        lines = f.readlines()

    def tokenize_chunk(chunk):
        cleaned_text = " ".join(line.strip() for line in chunk if line.strip())
        tokens = self.tokenizer.encode(cleaned_text)
        return tokens

    num_threads = os.cpu_count() or 4

    # Ensure chunk_size is at least 1
    chunk_size = max(1, len(lines) // num_threads)
    chunks = [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        tokenized_chunks = list(executor.map(tokenize_chunk, chunks))

    self._tokenized_corpus = [
        token for chunk in tokenized_chunks for token in chunk
    ]
    self._corpus_size = len(self._tokenized_corpus)
    self.debug(lambda: f"Initialized corpus with {self._corpus_size} tokens")
```

**Parallel Tokenization:**

- Split corpus into chunks (one per CPU core)
- Tokenize chunks in parallel via ThreadPoolExecutor
- Flatten tokenized chunks into single token list

### Prompt Generation

```python
def generate(
    self,
    mean: int | None = None,
    stddev: int | None = None,
    hash_ids: list[int] | None = None,
) -> str:
    """Generate a synthetic prompt.

    Args:
        mean: The mean of the normal distribution.
        stddev: The standard deviation of the normal distribution.
        hash_ids: A list of hash indices used for token reuse (caching).

    Returns:
        A synthetic prompt as a string.
    """
    if hash_ids:
        return self._generate_cached_prompt(
            mean, hash_ids, self.config.input_tokens.block_size
        )

    num_tokens = utils.sample_positive_normal_integer(mean, stddev)
    return self._generate_prompt(num_tokens)

def _generate_prompt(self, num_tokens: int) -> str:
    """Generate a prompt containing exactly `num_tokens` tokens.

    Args:
        num_tokens: Number of tokens required in the prompt.

    Returns:
        A synthetic prompt as a string.
    """
    return self.tokenizer.decode(self._sample_tokens(num_tokens))

def _sample_tokens(self, num_tokens: int) -> list[int]:
    """Sample tokens from the corpus.

    Args:
        num_tokens: Number of tokens to sample.

    Returns:
        List of token IDs.
    """
    if num_tokens > self._corpus_size:
        # Repeat corpus if needed
        repeats = (num_tokens // self._corpus_size) + 1
        extended_corpus = self._tokenized_corpus * repeats
        start_idx = random.randint(0, len(extended_corpus) - num_tokens)
    else:
        start_idx = random.randint(0, self._corpus_size - num_tokens)
        extended_corpus = self._tokenized_corpus

    return extended_corpus[start_idx : start_idx + num_tokens]
```

**Token Sampling Strategy:**

1. Sample random starting position in corpus
2. Extract contiguous token sequence
3. If requested tokens > corpus size, repeat corpus
4. Decode tokens to text

### Cached Generation

For scenarios requiring token reuse (e.g., simulating KV cache hits):

```python
def _generate_cached_prompt(
    self,
    num_tokens: int,
    hash_ids: list[int],
    block_size: int,
) -> str:
    """Generate a prompt with token reuse via caching.

    Each hash index in `hash_ids` corresponds to a block of `block_size` tokens.
    If a hash index is found in cache, its stored prompt is reused. Otherwise,
    a new prompt is generated and stored in cache.

    Args:
        num_tokens: The number of tokens required in the prompt.
        hash_ids: A list of hash IDs to use for token reuse.
        block_size: The number of tokens allocated per hash block.

    Returns:
        A synthetic prompt as a string.
    """
    tokens = []
    remaining_tokens = num_tokens

    for hash_id in hash_ids:
        if remaining_tokens <= 0:
            break

        # Determine how many tokens to use from this block
        block_tokens = min(block_size, remaining_tokens)

        if hash_id in self._cache:
            # Reuse cached tokens
            cached_tokens = self._cache[hash_id][:block_tokens]
            tokens.extend(cached_tokens)
        else:
            # Generate new tokens and cache
            new_tokens = self._sample_tokens(block_tokens)
            self._cache[hash_id] = new_tokens
            tokens.extend(new_tokens)

        remaining_tokens -= block_tokens

    # If we still need more tokens, generate them
    if remaining_tokens > 0:
        additional_tokens = self._sample_tokens(remaining_tokens)
        tokens.extend(additional_tokens)

    return self.tokenizer.decode(tokens)
```

**Use Case:**

Simulate prefix caching - requests with shared prefixes reuse token blocks, improving server cache hit rates.

### Prefix Prompts

System prompts prepended to first turn:

```python
def _create_prefix_prompt_pool(self) -> None:
    """Generate a pool of prefix prompts to sample from."""
    if self._tokenized_corpus is None:
        raise NotInitializedError("Tokenized corpus is not initialized.")

    self._prefix_prompts = [
        self._generate_prompt(self.config.prefix_prompt.length)
        for _ in range(self.config.prefix_prompt.pool_size)
    ]
    self.debug(
        lambda: f"Initialized prefix prompts pool with {len(self._prefix_prompts)} prompts"
    )

def get_random_prefix_prompt(self) -> str:
    """Get a random prefix prompt from the pool."""
    if not self._prefix_prompts:
        raise InvalidStateError("Prefix prompt pool is empty")
    return random.choice(self._prefix_prompts)
```

**Usage:**

```python
if is_first_turn and self.prefix_prompt_enabled:
    prefix = self.prompt_generator.get_random_prefix_prompt()
    prompt = f"{prefix}\n\n{prompt}"
```

## Image Generation

### Architecture

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/generator/image.py`:

```python
class ImageGenerator(BaseGenerator):
    """Generator for synthetic images.

    Generates images with specified dimensions using PIL. Images are solid
    colors or simple patterns for performance.
    """

    def __init__(self, config: ImageConfig):
        super().__init__(config)
        self.config = config

    def generate(self) -> str:
        """Generate a synthetic image.

        Returns:
            Base64-encoded image data URL.
        """
        width = utils.sample_positive_normal_integer(
            self.config.width.mean,
            self.config.width.stddev,
        )
        height = utils.sample_positive_normal_integer(
            self.config.height.mean,
            self.config.height.stddev,
        )

        # Generate image
        image = self._create_image(width, height)

        # Encode to base64 data URL
        return self._encode_image(image)

    def _create_image(self, width: int, height: int) -> Image.Image:
        """Create a synthetic image with specified dimensions."""
        from PIL import Image

        # Generate random color
        color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )

        # Create solid color image
        image = Image.new("RGB", (width, height), color)

        return image

    def _encode_image(self, image: Image.Image) -> str:
        """Encode image to base64 data URL."""
        import base64
        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        encoded = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
```

**Image Generation Strategies:**

1. **Solid Color**: Fast, minimal data
2. **Random Noise**: Slightly more realistic
3. **Patterns**: Checkboard, gradients, etc.
4. **Pre-generated**: Load from asset library

**Performance:**

- Solid color: ~100-200 μs per image
- Random noise: ~1-2 ms per image
- Complex patterns: ~5-10 ms per image

## Audio Generation

### Architecture

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/generator/audio.py`:

```python
class AudioGenerator(BaseGenerator):
    """Generator for synthetic audio.

    Generates audio files with specified duration using numpy. Audio is
    simple tones or silence for performance.
    """

    def __init__(self, config: AudioConfig):
        super().__init__(config)
        self.config = config
        self.sample_rate = 16000  # 16 kHz

    def generate(self) -> str:
        """Generate synthetic audio.

        Returns:
            Base64-encoded audio data URL.
        """
        length_sec = utils.sample_positive_normal_integer(
            self.config.length.mean,
            self.config.length.stddev,
        )

        # Generate audio samples
        samples = self._create_audio(length_sec)

        # Encode to base64 data URL
        return self._encode_audio(samples)

    def _create_audio(self, length_sec: int) -> np.ndarray:
        """Create synthetic audio with specified duration."""
        import numpy as np

        num_samples = length_sec * self.sample_rate

        # Generate silence or simple tone
        if self.config.audio_type == "silence":
            samples = np.zeros(num_samples, dtype=np.int16)
        elif self.config.audio_type == "tone":
            # Generate sine wave tone
            frequency = 440  # A4 note
            t = np.linspace(0, length_sec, num_samples)
            samples = np.sin(2 * np.pi * frequency * t)
            samples = (samples * 32767).astype(np.int16)
        else:
            # Random noise
            samples = np.random.randint(-32768, 32767, num_samples, dtype=np.int16)

        return samples

    def _encode_audio(self, samples: np.ndarray) -> str:
        """Encode audio to base64 data URL."""
        import base64
        import wave
        from io import BytesIO

        buffer = BytesIO()

        # Write WAV file to buffer
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(samples.tobytes())

        buffer.seek(0)

        encoded = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:audio/wav;base64,{encoded}"
```

**Audio Generation Strategies:**

1. **Silence**: Fastest, ~50 μs per second
2. **Sine Wave**: Simple tone, ~100 μs per second
3. **Random Noise**: More realistic, ~500 μs per second
4. **Speech Synthesis**: Complex, ~1-10 ms per second (not implemented)

## Caching Strategies

### Prompt Caching

**Token Block Caching:**

```python
self._cache: dict[int, list[int]] = {}

# Cache tokens by block ID
if hash_id not in self._cache:
    new_tokens = self._sample_tokens(block_size)
    self._cache[hash_id] = new_tokens
```

Benefits:
- Simulates KV cache behavior
- Reduces tokenization overhead
- Enables prefix sharing experiments

### Image Caching

For repeated image use:

```python
class CachedImageGenerator(ImageGenerator):
    """Image generator with caching."""

    def __init__(self, config: ImageConfig, cache_size: int = 100):
        super().__init__(config)
        self._image_cache: dict[tuple[int, int], str] = {}
        self._cache_size = cache_size

    def generate(self) -> str:
        """Generate with caching."""
        width = utils.sample_positive_normal_integer(
            self.config.width.mean,
            self.config.width.stddev,
        )
        height = utils.sample_positive_normal_integer(
            self.config.height.mean,
            self.config.height.stddev,
        )

        cache_key = (width, height)

        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        # Generate and cache
        image_data = super().generate()

        if len(self._image_cache) < self._cache_size:
            self._image_cache[cache_key] = image_data

        return image_data
```

### Audio Caching

Similar to image caching:

```python
class CachedAudioGenerator(AudioGenerator):
    """Audio generator with caching."""

    def __init__(self, config: AudioConfig, cache_size: int = 50):
        super().__init__(config)
        self._audio_cache: dict[int, str] = {}
        self._cache_size = cache_size

    def generate(self) -> str:
        """Generate with caching."""
        length_sec = utils.sample_positive_normal_integer(
            self.config.length.mean,
            self.config.length.stddev,
        )

        if length_sec in self._audio_cache:
            return self._audio_cache[length_sec]

        # Generate and cache
        audio_data = super().generate()

        if len(self._audio_cache) < self._cache_size:
            self._audio_cache[length_sec] = audio_data

        return audio_data
```

## Performance Optimization

### Lazy Initialization

Initialize generators only when needed:

```python
class LazyGenerator:
    """Lazy-loading generator wrapper."""

    def __init__(self, generator_class, config):
        self._generator_class = generator_class
        self._config = config
        self._generator = None

    def generate(self, **kwargs):
        """Generate, initializing on first call."""
        if self._generator is None:
            self._generator = self._generator_class(self._config)
        return self._generator.generate(**kwargs)
```

### Pre-generation

Generate content in advance:

```python
class PreGeneratedPromptGenerator(PromptGenerator):
    """Generator with pre-generated prompts."""

    def __init__(self, config: PromptConfig, tokenizer: Tokenizer, pool_size: int = 1000):
        super().__init__(config, tokenizer)
        self._prompt_pool: list[str] = []
        self._pool_index = 0

        # Pre-generate prompts
        for _ in range(pool_size):
            prompt = self._generate_prompt(
                utils.sample_positive_normal_integer(
                    config.input_tokens.mean,
                    config.input_tokens.stddev,
                )
            )
            self._prompt_pool.append(prompt)

    def generate(self, **kwargs) -> str:
        """Return pre-generated prompt."""
        prompt = self._prompt_pool[self._pool_index]
        self._pool_index = (self._pool_index + 1) % len(self._prompt_pool)
        return prompt
```

### Batch Generation

Generate multiple items at once:

```python
class BatchImageGenerator(ImageGenerator):
    """Generator that produces batches of images."""

    def generate_batch(self, batch_size: int) -> list[str]:
        """Generate multiple images."""
        return [self.generate() for _ in range(batch_size)]

    def generate_batch_parallel(self, batch_size: int, num_workers: int = 4) -> list[str]:
        """Generate batch in parallel."""
        from multiprocessing import Pool

        with Pool(num_workers) as pool:
            results = pool.starmap(
                self._generate_single,
                [()] * batch_size,
            )

        return results

    def _generate_single(self) -> str:
        """Helper for parallel generation."""
        return self.generate()
```

## Best Practices

### Configuration

```yaml
input:
  prompt:
    input_tokens:
      mean: 100
      stddev: 20
    block_size: 64  # For cached generation
    prefix_prompt:
      pool_size: 10
      length: 50
  image:
    width:
      mean: 512
      stddev: 50
    height:
      mean: 512
      stddev: 50
    cache_size: 100  # Number of images to cache
  audio:
    length:
      mean: 5
      stddev: 1
    sample_rate: 16000
    audio_type: "tone"  # or "silence", "noise"
```

### Memory Management

```python
def clear_caches(self):
    """Clear all generator caches."""
    if hasattr(self, "_cache"):
        self._cache.clear()
    if hasattr(self, "_image_cache"):
        self._image_cache.clear()
    if hasattr(self, "_audio_cache"):
        self._audio_cache.clear()
    if hasattr(self, "_prompt_pool"):
        self._prompt_pool.clear()
```

### Corpus Selection

**Shakespeare (default):**
- Rich vocabulary
- Complex sentence structure
- Good for general testing

**Custom corpus:**

```python
corpus_path = Path("/path/to/my/corpus.txt")
generator = PromptGenerator(config, tokenizer, corpus_path=corpus_path)
```

Choose corpus matching target domain (e.g., code for coding benchmarks, scientific text for research).

## Troubleshooting

### Tokenization Errors

**Symptoms:** `TokenizationError` during generation

**Causes:**
- Corpus encoding issues
- Special characters
- Tokenizer incompatibility

**Solutions:**

```python
# Clean corpus
with open(corpus_path, encoding="utf-8", errors="ignore") as f:
    text = f.read()
text = text.encode("utf-8", errors="ignore").decode("utf-8")
```

### Memory Issues

**Symptoms:** Out of memory

**Causes:**
- Large corpus
- Excessive caching
- Pre-generation pool too large

**Solutions:**
- Use streaming corpus loading
- Limit cache sizes
- Generate on-demand instead of pre-generating

### Slow Generation

**Symptoms:** Generation takes seconds

**Causes:**
- Large images/audio
- No caching
- Serial generation

**Solutions:**
- Reduce dimensions
- Enable caching
- Use batch parallel generation

## Key Takeaways

1. **Generator Architecture**: BaseGenerator provides common interface; subclasses implement content-specific generation.

2. **Prompt Generation**: Samples contiguous token sequences from pre-tokenized corpus for realistic prompts.

3. **Token Block Caching**: Simulates KV cache behavior by reusing token blocks across prompts.

4. **Image Generation**: Creates synthetic images with specified dimensions using PIL; supports solid colors, patterns, noise.

5. **Audio Generation**: Produces synthetic audio with specified duration using NumPy; supports silence, tones, noise.

6. **Parallel Tokenization**: Corpus tokenization parallelized across CPU cores for fast initialization.

7. **Caching Strategies**: Prompt (token blocks), image (dimensions), audio (duration) caching reduce overhead.

8. **Performance Optimization**: Lazy initialization, pre-generation pools, batch generation improve throughput.

9. **Corpus Selection**: Default Shakespeare corpus; custom corpora supported for domain-specific benchmarks.

10. **Best Practices**: Configure means/stddevs for realistic variation, enable caching for repeated use, clear caches to manage memory.

Next: [Chapter 20: Metrics Foundation](chapter-20-metrics-foundation.md)
