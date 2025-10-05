# Chapter 30: UserConfig Deep Dive

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Navigation
- Previous: [Chapter 29: Configuration Architecture](chapter-29-configuration-architecture.md)
- [Table of Contents](README.md)

## Overview

This chapter provides a comprehensive reference for UserConfig and all nested configurations. It covers every field, validation rule, default value, and usage example for complete mastery of AIPerf configuration.

## UserConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/user_config.py`

Top-level configuration containing all benchmark settings.

```python
class UserConfig(BaseConfig):
    """A configuration class for defining top-level user settings."""

    endpoint: EndpointConfig        # Required
    input: InputConfig = InputConfig()
    output: OutputConfig = OutputConfig()
    tokenizer: TokenizerConfig = TokenizerConfig()
    loadgen: LoadGeneratorConfig = LoadGeneratorConfig()
    cli_command: str | None = None  # Auto-generated
```

### Key Properties

**timing_mode**: Computed timing strategy
```python
@property
def timing_mode(self) -> TimingMode:
    """Get the timing mode based on configuration."""
    # Returns: REQUEST_RATE or FIXED_SCHEDULE
```

Values:
- `TimingMode.REQUEST_RATE`: Rate-based or concurrency-based
- `TimingMode.FIXED_SCHEDULE`: Timestamp-based replay

## EndpointConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/endpoint_config.py`

Endpoint and model configuration.

### Required Fields

**model_names**: Model(s) to benchmark
```python
model_names: list[str]  # Required
```

CLI: `--model-names`, `--model`, `-m`

Examples:
```bash
--model-names gpt-4
--model-names gpt-4,gpt-3.5-turbo  # Multiple models
```

### Endpoint Settings

**url**: API endpoint URL
```python
url: str = "http://localhost:8000"
```

CLI: `--url`, `-u`

**type**: Endpoint type
```python
type: EndpointType = EndpointType.CHAT
```

CLI: `--endpoint-type`

Values:
- `CHAT`: `/v1/chat/completions`
- `COMPLETIONS`: `/v1/completions`
- `EMBEDDINGS`: `/v1/embeddings`
- `RANKINGS`: `/v1/rankings`
- `RESPONSES`: Custom responses endpoint

**streaming**: Enable streaming
```python
streaming: bool = False
```

CLI: `--streaming`

**custom_endpoint**: Override default endpoint path
```python
custom_endpoint: str | None = None
```

CLI: `--custom-endpoint`, `--endpoint`

### Authentication

**api_key**: API authentication key
```python
api_key: str | None = None
```

CLI: `--api-key`

Format: `Bearer {api_key}` header

### Timeouts

**timeout_seconds**: Request timeout
```python
timeout_seconds: float = 300.0
```

CLI: `--request-timeout-seconds`

### Model Selection

**model_selection_strategy**: Multi-model assignment
```python
model_selection_strategy: ModelSelectionStrategy = ROUND_ROBIN
```

CLI: `--model-selection-strategy`

Values:
- `ROUND_ROBIN`: Nth prompt → n mod len(models)
- `RANDOM`: Uniform random assignment

## InputConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/input_config.py`

Input data and stimulus configuration.

### Dataset Options

**file**: Input dataset file
```python
file: Path | None = None
```

CLI: `--input-file`

**public_dataset**: Public dataset name
```python
public_dataset: PublicDatasetType | None = None
```

CLI: `--public-dataset`

**custom_dataset_type**: Custom dataset format
```python
custom_dataset_type: CustomDatasetType | None = None
```

CLI: `--custom-dataset-type`

Values:
- `SINGLE_TURN`: Single request-response pairs
- `MULTI_TURN`: Conversation threads
- `RANDOM_POOL`: Random selection from pool
- `MOONCAKE_TRACE`: Trace replay format

### Fixed Schedule

**fixed_schedule**: Enable timestamp-based replay
```python
fixed_schedule: bool = False
```

CLI: `--fixed-schedule`

**fixed_schedule_auto_offset**: Auto-adjust timestamps
```python
fixed_schedule_auto_offset: bool = False
```

CLI: `--fixed-schedule-auto-offset`

**fixed_schedule_start_offset**: Start timestamp (ms)
```python
fixed_schedule_start_offset: int | None = None
```

CLI: `--fixed-schedule-start-offset`

**fixed_schedule_end_offset**: End timestamp (ms)
```python
fixed_schedule_end_offset: int | None = None
```

CLI: `--fixed-schedule-end-offset`

### Extra Parameters

**extra**: Additional request parameters
```python
extra: list[tuple[str, Any]] = []
```

CLI: `--extra-inputs`

Format: `key:value` or JSON dict

**headers**: Custom HTTP headers
```python
headers: list[tuple[str, str]] = []
```

CLI: `--header`, `-H`

Format: `Header:Value`

### Goodput SLOs

**goodput**: Service level objectives
```python
goodput: dict[str, float] | None = None
```

CLI: `--goodput`

Format: `metric_tag:threshold`

Examples:
```bash
--goodput request_latency:250 inter_token_latency:10
```

### Random Seed

**random_seed**: Deterministic generation
```python
random_seed: int | None = None
```

CLI: `--random-seed`

### Nested Configs

**prompt**: Prompt generation settings
```python
prompt: PromptConfig = PromptConfig()
```

**image**: Image input settings
```python
image: ImageConfig = ImageConfig()
```

**audio**: Audio input settings
```python
audio: AudioConfig = AudioConfig()
```

**conversation**: Multi-turn settings
```python
conversation: ConversationConfig = ConversationConfig()
```

## PromptConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/prompt_config.py`

Synthetic prompt generation configuration.

### Input Tokens

**input_tokens.mean**: Average input length
```python
input_tokens.mean: int = 100
```

CLI: `--prompt-input-tokens-mean`, `--isl`

**input_tokens.stddev**: Input length variability
```python
input_tokens.stddev: float = 0.0
```

CLI: `--prompt-input-tokens-stddev`

**input_tokens.block_size**: Prompt block size
```python
input_tokens.block_size: int = 512
```

CLI: `--prompt-input-tokens-block-size`

### Output Tokens

**output_tokens.mean**: Average output length
```python
output_tokens.mean: int | None = None
```

CLI: `--prompt-output-tokens-mean`, `--osl`

**output_tokens.stddev**: Output length variability
```python
output_tokens.stddev: float = 0.0
```

CLI: `--prompt-output-tokens-stddev`

**output_tokens.deterministic**: Fixed output length
```python
output_tokens.deterministic: bool = False
```

CLI: `--prompt-output-tokens-deterministic`

### Prefix Prompt

**prefix_prompt**: Prompt prefix text
```python
prefix_prompt: str | None = None
```

CLI: `--prefix-prompt`

## OutputConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/output_config.py`

Output and artifact configuration.

**artifact_directory**: Output directory
```python
artifact_directory: Path = Path("artifacts")
```

CLI: `--output-artifact-dir`, `--artifact-dir`

Auto-computed path:
```
artifacts/{model}-{service}-{stimulus}/
```

## TokenizerConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/tokenizer_config.py`

Tokenizer configuration for token counting.

**model**: Tokenizer model name
```python
model: str | None = None
```

CLI: `--tokenizer`

**trust_remote_code**: Allow remote code execution
```python
trust_remote_code: bool = False
```

CLI: `--tokenizer-trust-remote-code`

**revision**: Model revision/branch
```python
revision: str = "main"
```

CLI: `--tokenizer-revision`

## LoadGeneratorConfig

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/loadgen_config.py`

Load generation parameters.

### Benchmark Mode

**request_count**: Number of requests
```python
request_count: int = 100
```

CLI: `--request-count`, `--num-requests`

**benchmark_duration**: Duration in seconds
```python
benchmark_duration: float | None = None
```

CLI: `--benchmark-duration`

Validation: Cannot use both request_count and benchmark_duration

**benchmark_grace_period**: Post-duration wait time
```python
benchmark_grace_period: float = 5.0
```

CLI: `--benchmark-grace-period`

### Load Strategy

**concurrency**: Concurrent requests
```python
concurrency: int | None = None
```

CLI: `--concurrency`

**request_rate**: Target rate (req/s)
```python
request_rate: float | None = None
```

CLI: `--request-rate`

**request_rate_mode**: Rate generation mode
```python
request_rate_mode: RequestRateMode = CONSTANT
```

CLI: `--request-rate-mode`

Values:
- `CONSTANT`: Fixed rate
- `POISSON`: Poisson distribution
- `CONCURRENCY_BURST`: Max concurrency (internal)

### Warmup

**warmup_request_count**: Warmup requests
```python
warmup_request_count: int = 0
```

CLI: `--warmup-request-count`, `--num-warmup-requests`

### Request Cancellation

**request_cancellation_rate**: Cancellation percentage
```python
request_cancellation_rate: float = 0.0
```

CLI: `--request-cancellation-rate`

Range: 0.0 - 100.0

**request_cancellation_delay**: Delay before cancel (s)
```python
request_cancellation_delay: float = 0.0
```

CLI: `--request-cancellation-delay`

## Configuration Examples

### Basic Chat Benchmark

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="https://api.openai.com/v1/chat/completions",
        model_names=["gpt-4"],
        streaming=True,
        api_key="sk-...",
    ),
    loadgen=LoadGeneratorConfig(
        request_count=1000,
        concurrency=10,
    ),
)
```

### Rate-Based Load

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="http://localhost:8000/v1/chat/completions",
        model_names=["llama-2-7b"],
    ),
    loadgen=LoadGeneratorConfig(
        request_rate=50.0,  # 50 req/s
        request_rate_mode=RequestRateMode.POISSON,
        benchmark_duration=60.0,  # 60 seconds
    ),
)
```

### Synthetic Dataset

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="http://localhost:8000/v1/chat/completions",
        model_names=["gpt-3.5-turbo"],
    ),
    input=InputConfig(
        prompt=PromptConfig(
            input_tokens=InputTokensConfig(
                mean=512,
                stddev=128,
            ),
            output_tokens=OutputTokensConfig(
                mean=256,
                stddev=64,
            ),
        ),
    ),
    loadgen=LoadGeneratorConfig(
        request_count=500,
        concurrency=5,
    ),
)
```

### Custom Dataset

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="http://localhost:8000/v1/chat/completions",
        model_names=["custom-model"],
    ),
    input=InputConfig(
        file=Path("dataset.jsonl"),
        custom_dataset_type=CustomDatasetType.SINGLE_TURN,
    ),
    loadgen=LoadGeneratorConfig(
        request_count=1000,
    ),
)
```

### Trace Replay

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="http://localhost:8000/v1/chat/completions",
        model_names=["model"],
    ),
    input=InputConfig(
        file=Path("trace.jsonl"),
        custom_dataset_type=CustomDatasetType.MOONCAKE_TRACE,
        fixed_schedule=True,
        fixed_schedule_auto_offset=True,
    ),
)
```

### Goodput Measurement

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="http://localhost:8000/v1/chat/completions",
        model_names=["gpt-4"],
        streaming=True,
    ),
    input=InputConfig(
        goodput={
            "request_latency": 250,  # 250ms SLO
            "inter_token_latency": 10,  # 10ms SLO
        },
    ),
    loadgen=LoadGeneratorConfig(
        request_count=1000,
        concurrency=10,
    ),
)
```

## Validation Rules

### Field-Level

- **Positive values**: `ge=1` for counts, `gt=0` for rates
- **Range limits**: `ge=0, le=100` for percentages
- **Type checking**: Automatic via Pydantic

### Cross-Field

**Benchmark Mode**:
```python
# Cannot use both
if benchmark_duration and request_count:
    raise ValueError("Use either --request-count or --benchmark-duration")
```

**Grace Period**:
```python
# Requires duration mode
if benchmark_grace_period and not benchmark_duration:
    raise ValueError("--benchmark-grace-period requires --benchmark-duration")
```

**Fixed Schedule**:
```python
# Requires input file
if fixed_schedule and not file:
    raise ValueError("Fixed schedule requires --input-file")
```

**Schedule Offsets**:
```python
# Cannot use both
if fixed_schedule_start_offset and fixed_schedule_auto_offset:
    raise ValueError("Cannot use both offset modes")
```

## Default Values

### EndpointConfig
- url: `"http://localhost:8000"`
- type: `EndpointType.CHAT`
- streaming: `False`
- timeout_seconds: `300.0`
- model_selection_strategy: `ROUND_ROBIN`

### InputConfig
- All nested configs use their defaults

### OutputConfig
- artifact_directory: `Path("artifacts")`

### LoadGeneratorConfig
- request_count: `100`
- warmup_request_count: `0`
- concurrency: `None` (auto-set to 1 if needed)
- request_rate: `None`
- request_rate_mode: `CONSTANT`
- benchmark_duration: `None`
- benchmark_grace_period: `5.0`
- request_cancellation_rate: `0.0`
- request_cancellation_delay: `0.0`

### PromptConfig
- input_tokens.mean: `100`
- input_tokens.stddev: `0.0`
- input_tokens.block_size: `512`
- output_tokens.mean: `None`
- output_tokens.stddev: `0.0`
- output_tokens.deterministic: `False`

## YAML Configuration

### Complete Example

```yaml
endpoint:
    url: https://api.openai.com/v1/chat/completions
    model_names:
        - gpt-4
    type: chat
    streaming: true
    timeout_seconds: 300.0
    api_key: sk-...

input:
    prompt:
        input_tokens:
            mean: 512
            stddev: 128
        output_tokens:
            mean: 256
            stddev: 64
    goodput:
        request_latency: 250
        inter_token_latency: 10

output:
    artifact_directory: ./results

loadgen:
    request_count: 1000
    concurrency: 10
    warmup_request_count: 10
```

### Loading YAML

```python
import yaml
from pathlib import Path

# Load
config_path = Path("config.yaml")
with open(config_path) as f:
    config_dict = yaml.safe_load(f)

# Create
config = UserConfig(**config_dict)
```

### Generating Template

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="https://api.example.com",
        model_names=["model-name"],
    )
)

# Generate with comments
template = config.serialize_to_yaml(verbose=True)

# Save
with open("template.yaml", "w") as f:
    f.write(template)
```

## CLI Command Reconstruction

AIPerf saves the CLI command used:

```python
config.cli_command
# "aiperf --url https://api.openai.com --model-names gpt-4 --request-count 1000"
```

Auto-generated for reproducibility and auditing.

## Key Takeaways

1. **Hierarchical Structure**: Organized into logical configuration groups

2. **Type Safety**: Pydantic enforces types and constraints

3. **Validation**: Field-level and cross-field validation ensures correctness

4. **Defaults**: Sensible defaults for quick setup

5. **CLI Mapping**: Every field accessible via CLI parameters

6. **Multiple Names**: Legacy compatibility with GenAI-Perf

7. **YAML Support**: Human-readable configuration files

8. **Documentation**: Field descriptions serve as inline docs

9. **Flexibility**: Supports various benchmarking scenarios

10. **Reproducibility**: CLI command saved for audit trail

## Configuration Cheat Sheet

### Quick Reference

| Use Case | Key Settings |
|----------|--------------|
| Basic benchmark | `model_names`, `request_count`, `concurrency` |
| Rate-based load | `request_rate`, `request_rate_mode`, `benchmark_duration` |
| Streaming | `streaming=True`, goodput SLOs |
| Custom dataset | `file`, `custom_dataset_type` |
| Trace replay | `fixed_schedule`, `fixed_schedule_auto_offset` |
| Synthetic data | `prompt.input_tokens`, `prompt.output_tokens` |
| Authentication | `api_key`, custom `headers` |
| Timeout control | `timeout_seconds` |
| Warmup | `warmup_request_count` |
| Multi-model | `model_names` (list), `model_selection_strategy` |

## What's Next

You've completed the AIPerf Developer's Guidebook! You now have comprehensive knowledge of:

- Metrics architecture (Chapters 21-22)
- HTTP and OpenAI clients (Chapters 23-24)
- SSE streaming and TCP optimizations (Chapters 25-26)
- Request/response handling (Chapters 27-28)
- Configuration system (Chapters 29-30)

---

**Remember**: Configuration is the interface to AIPerf's powerful benchmarking capabilities. Master these settings to unlock precise, reproducible performance measurements for any AI workload.
