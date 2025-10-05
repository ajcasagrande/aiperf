# Chapter 29: Configuration Architecture

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Navigation
- Previous: [Chapter 28: Response Parsers](chapter-28-response-parsers.md)
- Next: [Chapter 30: UserConfig Deep Dive](chapter-30-userconfig-deep-dive.md)
- [Table of Contents](README.md)

## Overview

AIPerf's configuration system is built on Pydantic v2, providing type-safe, validated, and self-documenting configuration with automatic CLI parameter mapping. The hierarchical configuration structure enables organized settings management while maintaining flexibility for different use cases.

This chapter explores the configuration architecture, Pydantic integration, validation system, CLI parameter mapping, and YAML serialization.

## Architecture

### Configuration Hierarchy

```
UserConfig (Top Level)
├── EndpointConfig        # API endpoint settings
├── InputConfig           # Input data configuration
│   ├── PromptConfig      # Prompt generation
│   ├── ImageConfig       # Image input settings
│   ├── AudioConfig       # Audio input settings
│   └── ConversationConfig # Multi-turn conversations
├── OutputConfig          # Output and artifacts
├── TokenizerConfig       # Tokenization settings
└── LoadGeneratorConfig   # Load generation parameters
```

### BaseConfig Class

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/base_config.py`

```python
class BaseConfig(BaseModel):
    """Base configuration class for all configurations."""

    def serialize_to_yaml(self, verbose: bool = False, indent: int = 4) -> str:
        """Serialize a Pydantic model to a YAML string.

        Args:
            verbose: Whether to include verbose comments in the YAML output.
            indent: The per-level indentation to use.
        """
        context = {"verbose": verbose}
        data = self.model_dump(context=context)

        # Attach comments recursively
        commented_data = self._attach_comments(
            data=data,
            model=self,
            context=context,
            indent=indent,
        )

        # Dump to YAML
        yaml = YAML(pure=True)
        yaml.indent(mapping=indent, sequence=indent, offset=indent)

        stream = io.StringIO()
        yaml.dump(commented_data, stream)
        return stream.getvalue()
```

**Key Features**:
1. **Pydantic BaseModel**: Type validation and serialization
2. **YAML Serialization**: Human-readable config files
3. **Comment Attachment**: Field descriptions as YAML comments
4. **Recursive Processing**: Handles nested configurations

## Pydantic Integration

### Type Validation

Pydantic automatically validates types:

```python
from pydantic import Field
from typing import Annotated

class EndpointConfig(BaseConfig):
    timeout_seconds: Annotated[
        float,
        Field(
            description="The timeout in floating-point seconds for each request.",
        ),
    ] = 30.0  # Default value

# Valid
config = EndpointConfig(timeout_seconds=10.5)  # ✓

# Invalid - raises ValidationError
config = EndpointConfig(timeout_seconds="invalid")  # ✗ TypeError
```

### Field Validation

Custom validators enforce constraints:

```python
class LoadGeneratorConfig(BaseConfig):
    concurrency: Annotated[
        int | None,
        Field(
            ge=1,  # Greater than or equal to 1
            description="The concurrency value to benchmark.",
        ),
    ] = None

# Valid
config = LoadGeneratorConfig(concurrency=10)  # ✓

# Invalid - raises ValidationError
config = LoadGeneratorConfig(concurrency=0)  # ✗ Must be >= 1
config = LoadGeneratorConfig(concurrency=-5)  # ✗ Must be >= 1
```

### Model Validators

Complex validation logic:

```python
from pydantic import model_validator
from typing_extensions import Self

class UserConfig(BaseConfig):
    @model_validator(mode="after")
    def validate_benchmark_mode(self) -> Self:
        """Validate benchmarking is count-based or timing-based."""
        if (
            "benchmark_duration" in self.loadgen.model_fields_set
            and "request_count" in self.loadgen.model_fields_set
        ):
            raise ValueError(
                "Count-based and duration-based benchmarking cannot be used together."
            )
        return self
```

**Validation Modes**:
- `mode="before"`: Run before Pydantic validation
- `mode="after"`: Run after Pydantic validation

## CLI Parameter Mapping

### CLIParameter Annotation

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/cli_parameter.py`

```python
class CLIParameter:
    """Annotation for CLI parameter mapping."""

    def __init__(
        self,
        name: tuple[str, ...] | str,
        group: str | None = None,
        converter: Callable | None = None,
        consume_multiple: bool = False,
        show_choices: bool = True,
    ):
        self.name = name if isinstance(name, tuple) else (name,)
        self.group = group
        self.converter = converter
        self.consume_multiple = consume_multiple
        self.show_choices = show_choices
```

### Mapping Example

```python
class EndpointConfig(BaseConfig):
    _CLI_GROUP = Groups.ENDPOINT

    url: Annotated[
        str,
        Field(
            description="URL of the endpoint to target for benchmarking.",
        ),
        CLIParameter(
            name=(
                "--url",  # Primary name
                "-u",     # Short alias
            ),
            group=_CLI_GROUP,
        ),
    ] = "http://localhost:8000"
```

**CLI Usage**:
```bash
aiperf --url https://api.example.com/v1/chat/completions
aiperf -u https://api.example.com/v1/chat/completions  # Same result
```

### Multiple Names

Support for legacy names:

```python
request_count: Annotated[
    int,
    Field(description="The number of requests to use for measurement."),
    CLIParameter(
        name=(
            "--request-count",    # AIPerf name
            "--num-requests",     # GenAI-Perf legacy
        ),
        group=_CLI_GROUP,
    ),
] = 100
```

**Both work**:
```bash
aiperf --request-count 1000
aiperf --num-requests 1000  # Same result
```

### Parameter Groups

Organize CLI help output:

```python
class Groups:
    """CLI parameter groups."""
    ENDPOINT = "Endpoint Configuration"
    INPUT = "Input Configuration"
    OUTPUT = "Output Configuration"
    LOAD_GENERATOR = "Load Generator Configuration"
```

**Help Output**:
```
Endpoint Configuration:
  --url URL                 URL of the endpoint
  --model-names MODEL       Model name(s) to benchmark

Input Configuration:
  --input-file FILE         Dataset file path
  --random-seed SEED        Random seed for data generation
```

## Configuration Validation

### Field-Level Validation

```python
class LoadGeneratorConfig(BaseConfig):
    benchmark_duration: Annotated[
        float | None,
        Field(
            ge=1,  # Must be >= 1
            description="The duration in seconds for benchmarking.",
        ),
    ] = None

    request_rate: Annotated[
        float | None,
        Field(
            gt=0,  # Must be > 0
            description="Request rate in requests/second",
        ),
    ] = None
```

**Validators**:
- `ge`: Greater than or equal
- `gt`: Greater than
- `le`: Less than or equal
- `lt`: Less than

### Cross-Field Validation

```python
@model_validator(mode="after")
def validate_fixed_schedule(self) -> Self:
    """Validate the fixed schedule configuration."""
    if self.fixed_schedule and self.file is None:
        raise ValueError("Fixed schedule requires a file to be provided")
    return self
```

### Custom Validators

```python
from pydantic import BeforeValidator

def parse_str_or_list(value: str | list[str]) -> list[str]:
    """Convert comma-separated string to list."""
    if isinstance(value, str):
        return [v.strip() for v in value.split(",")]
    return value

class EndpointConfig(BaseConfig):
    model_names: Annotated[
        list[str],
        BeforeValidator(parse_str_or_list),
        Field(description="Model name(s) to be benchmarked."),
    ]

# Both work:
config = EndpointConfig(model_names="gpt-4,gpt-3.5-turbo")
config = EndpointConfig(model_names=["gpt-4", "gpt-3.5-turbo"])
```

## YAML Serialization

### Basic Serialization

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="https://api.openai.com/v1/chat/completions",
        model_names=["gpt-4"],
    ),
    loadgen=LoadGeneratorConfig(
        request_count=1000,
        concurrency=10,
    ),
)

yaml_str = config.serialize_to_yaml()
print(yaml_str)
```

**Output**:
```yaml
endpoint:
    url: https://api.openai.com/v1/chat/completions
    model_names:
        - gpt-4

loadgen:
    request_count: 1000
    concurrency: 10
```

### Verbose Mode

Include field descriptions as comments:

```python
yaml_str = config.serialize_to_yaml(verbose=True)
```

**Output**:
```yaml
endpoint:
    # URL of the endpoint to target for benchmarking.
    url: https://api.openai.com/v1/chat/completions

    # Model name(s) to be benchmarked.
    model_names:
        - gpt-4

loadgen:
    # The number of requests to use for measurement.
    request_count: 1000

    # The concurrency value to benchmark.
    concurrency: 10
```

### Comment Attachment

```python
@staticmethod
def _attach_comments(
    data: Any,
    model: BaseModel,
    context: dict,
    indent: int,
    indent_level: int = 0,
) -> Any:
    """Recursively attach comments from field descriptions."""
    if isinstance(data, dict):
        commented_map = CommentedMap()

        for field_name, value in data.items():
            field = model.__class__.model_fields.get(field_name)

            if BaseConfig._is_a_nested_config(field, value):
                # Recursively process nested models
                commented_map[field_name] = BaseConfig._attach_comments(
                    value,
                    getattr(model, field_name),
                    context=context,
                    indent=indent,
                    indent_level=indent_level + 1,
                )
            else:
                commented_map[field_name] = value

            # Attach comment if verbose and description exists
            if context.get("verbose") and field and field.description:
                commented_map.yaml_set_comment_before_after_key(
                    field_name,
                    before="\n" + field.description,
                    indent=indent * indent_level,
                )

        return commented_map
```

## Configuration Defaults

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/config_defaults.py`

```python
class EndpointDefaults:
    """Default values for EndpointConfig."""
    URL = "http://localhost:8000"
    TYPE = EndpointType.CHAT
    STREAMING = False
    TIMEOUT = 300.0
    API_KEY = None
    MODEL_SELECTION_STRATEGY = ModelSelectionStrategy.ROUND_ROBIN

class LoadGeneratorDefaults:
    """Default values for LoadGeneratorConfig."""
    REQUEST_COUNT = 100
    WARMUP_REQUEST_COUNT = 0
    CONCURRENCY = None
    REQUEST_RATE = None
    REQUEST_RATE_MODE = RequestRateMode.CONSTANT
    BENCHMARK_DURATION = None
    BENCHMARK_GRACE_PERIOD = 5.0
```

**Usage**:
```python
class EndpointConfig(BaseConfig):
    url: str = EndpointDefaults.URL
    timeout_seconds: float = EndpointDefaults.TIMEOUT
```

## Configuration Loading

### From CLI

```bash
aiperf \
  --url https://api.openai.com/v1/chat/completions \
  --model-names gpt-4 \
  --request-count 1000 \
  --concurrency 10
```

### From YAML

```python
from pathlib import Path
import yaml

# Load YAML
config_path = Path("config.yaml")
with open(config_path) as f:
    config_dict = yaml.safe_load(f)

# Create config
config = UserConfig(**config_dict)
```

### From Python

```python
config = UserConfig(
    endpoint=EndpointConfig(
        url="https://api.openai.com/v1/chat/completions",
        model_names=["gpt-4"],
        streaming=True,
    ),
    loadgen=LoadGeneratorConfig(
        request_count=1000,
        concurrency=10,
    ),
)
```

## Configuration Merging

### CLI Override Priority

```
Defaults < YAML File < CLI Arguments < Programmatic
```

**Example**:
```yaml
# config.yaml
loadgen:
    request_count: 1000
    concurrency: 10
```

```bash
# CLI overrides YAML
aiperf --config config.yaml --concurrency 20

# Result: request_count=1000 (from YAML), concurrency=20 (from CLI)
```

## Nested Configuration

### Accessing Nested Values

```python
config = UserConfig(...)

# Access nested values
url = config.endpoint.url
request_count = config.loadgen.request_count
input_tokens_mean = config.input.prompt.input_tokens.mean
```

### Modifying Nested Values

```python
# Create new nested config
config.endpoint = EndpointConfig(
    url="https://new-endpoint.com",
    model_names=["gpt-4"],
)

# Modify existing
config.loadgen.request_count = 2000
```

## Configuration Templates

### Generate Template

```python
# Create default config
config = UserConfig(
    endpoint=EndpointConfig(
        url="https://api.example.com",
        model_names=["model-name"],
    )
)

# Generate template with comments
template = config.serialize_to_yaml(verbose=True)

# Save to file
with open("config_template.yaml", "w") as f:
    f.write(template)
```

### Template Usage

```yaml
# config_template.yaml
endpoint:
    # URL of the endpoint to target for benchmarking.
    url: https://api.example.com

    # Model name(s) to be benchmarked. Can be a comma-separated list or a single model name.
    model_names:
        - model-name

    # The endpoint type to send requests to on the server.
    type: chat

    # An option to enable the use of the streaming API.
    streaming: false

loadgen:
    # The number of requests to use for measurement.
    request_count: 100

    # The concurrency value to benchmark.
    concurrency: null
```

## Key Takeaways

1. **Pydantic Foundation**: Type-safe configuration with automatic validation

2. **CLI Integration**: Seamless CLI parameter mapping with multiple names support

3. **Hierarchical Structure**: Organized nested configurations for different concerns

4. **YAML Serialization**: Human-readable config files with optional comments

5. **Validation**: Field-level and cross-field validation ensures correctness

6. **Defaults**: Sensible defaults defined in central location

7. **Extensible**: Easy to add new configuration fields and validators

8. **Documentation**: Field descriptions serve as inline documentation

9. **Type Inference**: Full IDE support with type hints

10. **Override Priority**: Clear precedence for configuration sources

## What's Next

- **Chapter 30: UserConfig Deep Dive** - Complete reference of all configuration fields

---

**Remember**: AIPerf's configuration architecture provides a robust foundation for type-safe, validated settings management. Understanding the Pydantic integration and CLI mapping enables effective configuration customization.
