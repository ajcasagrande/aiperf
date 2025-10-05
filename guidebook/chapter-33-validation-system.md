# Chapter 33: Validation System

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

AIPerf's validation system ensures configuration integrity and data correctness throughout the application lifecycle. Built on Pydantic's powerful validation framework, the system provides field-level validators, model-level validators, custom validation logic, and comprehensive error handling. This chapter explores the complete validation architecture, from basic field constraints to complex cross-field validation patterns.

The validation system operates at multiple levels: CLI input parsing, configuration model construction, runtime data validation, and service initialization. Each level provides specific guarantees about data quality and system state.

## Table of Contents

1. [Validation Architecture](#validation-architecture)
2. [Field Validation](#field-validation)
3. [Model Validators](#model-validators)
4. [Custom Validators](#custom-validators)
5. [Validator Utilities](#validator-utilities)
6. [Error Handling](#error-handling)
7. [Validation Patterns](#validation-patterns)
8. [Cross-Field Validation](#cross-field-validation)
9. [Conditional Validation](#conditional-validation)
10. [Validation Testing](#validation-testing)
11. [Best Practices](#best-practices)

## Validation Architecture

### Pydantic Validation Layers

AIPerf uses Pydantic's multi-layer validation system:

```
┌─────────────────────────────────────┐
│   CLI Input (Cyclopts)              │
│   - String parsing                  │
│   - Type conversion                 │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Field-Level Validation            │
│   - Type checking                   │
│   - Constraint validation (ge, le)  │
│   - Custom field validators         │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Model-Level Validation            │
│   - Cross-field validation          │
│   - Business logic validation       │
│   - Conditional validation          │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Runtime Validation                │
│   - Service initialization checks   │
│   - Resource availability           │
│   - Environment validation          │
└─────────────────────────────────────┘
```

### Validator Execution Order

Pydantic executes validators in this sequence:

1. **Before validators** (`mode="before"`): Run before type coercion
2. **Type coercion**: Convert input to target type
3. **Field validators**: Validate individual fields
4. **After validators** (`mode="after"`): Run after all fields are set
5. **Model construction**: Create the model instance

### Validation Module Structure

Validation utilities are located at `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/config_validators.py`.

## Field Validation

### Basic Field Constraints

Pydantic Field provides built-in constraint validation:

```python
from pydantic import Field
from typing import Annotated

class LoadConfig(BaseConfig):
    # Numeric constraints
    request_rate: Annotated[
        float,
        Field(
            ge=0,        # Greater than or equal to 0
            le=10000,    # Less than or equal to 10000
            description="Requests per second"
        )
    ] = 10.0

    # String constraints
    model_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            pattern=r"^[a-zA-Z0-9-_]+$",
            description="Model name"
        )
    ] = "gpt-4"

    # List constraints
    model_names: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=10,
            description="List of model names"
        )
    ] = Field(default_factory=lambda: ["gpt-4"])
```

### Numeric Validation

Validate numeric ranges and properties:

```python
from pydantic import Field

# Integer range
worker_count: Annotated[
    int,
    Field(ge=1, le=128, description="Number of workers")
] = 4

# Float range with step
temperature: Annotated[
    float,
    Field(ge=0.0, le=2.0, multiple_of=0.1, description="Sampling temperature")
] = 1.0

# Positive integers only
max_tokens: Annotated[
    int,
    Field(gt=0, description="Maximum tokens to generate")
] = 100
```

**Constraint Options**:
- `gt`: Greater than
- `ge`: Greater than or equal to
- `lt`: Less than
- `le`: Less than or equal to
- `multiple_of`: Value must be a multiple of this number

### String Validation

Validate string content and format:

```python
from pydantic import Field
import re

# Pattern matching
endpoint_url: Annotated[
    str,
    Field(
        pattern=r"^https?://",
        description="HTTP(S) endpoint URL"
    )
] = "http://localhost:8000"

# Length constraints
api_key: Annotated[
    str,
    Field(
        min_length=32,
        max_length=64,
        description="API key"
    )
]

# Whitespace handling
model_name: Annotated[
    str,
    Field(
        strip_whitespace=True,
        description="Model name (whitespace trimmed)"
    )
]
```

### List and Collection Validation

Validate lists and other collections:

```python
from pydantic import Field

# List size constraints
model_names: Annotated[
    list[str],
    Field(
        min_length=1,
        max_length=5,
        description="1-5 model names"
    )
]

# Unique items
unique_ids: Annotated[
    list[int],
    Field(
        unique_items=True,
        description="List of unique IDs"
    )
]

# Nested validation
coordinates: Annotated[
    list[tuple[float, float]],
    Field(
        min_length=1,
        description="List of (x, y) coordinates"
    )
]
```

### Path and File Validation

Validate file paths and existence:

```python
from pathlib import Path
from pydantic import Field, field_validator

class InputConfig(BaseConfig):
    dataset_path: Annotated[
        Path,
        Field(description="Path to dataset file")
    ]

    @field_validator("dataset_path")
    def validate_dataset_exists(cls, v: Path) -> Path:
        """Ensure dataset file exists."""
        if not v.exists():
            raise ValueError(f"Dataset file not found: {v}")
        if not v.is_file():
            raise ValueError(f"Dataset path is not a file: {v}")
        return v
```

### Optional Field Validation

Validate optional fields:

```python
from typing import Optional
from pydantic import Field

# Optional with default None
timeout: Optional[float] = Field(
    default=None,
    ge=0,
    description="Request timeout in seconds (optional)"
)

# Optional with default value
retry_count: Optional[int] = Field(
    default=3,
    ge=0,
    le=10,
    description="Number of retries"
)
```

## Model Validators

### Before Validators

Validators that run before type coercion:

```python
from pydantic import model_validator, Field
from typing import Any

class Config(BaseConfig):
    model_names: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    def parse_model_names(cls, data: Any) -> Any:
        """Parse model_names from string or list before type coercion."""
        if isinstance(data, dict) and "model_names" in data:
            value = data["model_names"]
            if isinstance(value, str):
                # Convert comma-separated string to list
                data["model_names"] = [
                    name.strip() for name in value.split(",")
                ]
        return data
```

**Use Cases for Before Validators**:
- Parse string inputs into complex types
- Normalize data formats
- Handle multiple input formats
- Preprocess raw configuration data

### After Validators

Validators that run after all fields are set:

```python
from pydantic import model_validator
from typing_extensions import Self

class ServiceConfig(BaseConfig):
    verbose: bool = False
    extra_verbose: bool = False
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_log_level_from_flags(self) -> Self:
        """Set log_level based on verbose flags."""
        if self.extra_verbose:
            self.log_level = "TRACE"
        elif self.verbose:
            self.log_level = "DEBUG"
        return self
```

**Use Cases for After Validators**:
- Cross-field validation
- Compute derived fields
- Apply business logic
- Ensure configuration consistency

### Communication Config Validator Example

Real-world validator from ServiceConfig:

```python
from pydantic import model_validator
from typing_extensions import Self

class ServiceConfig(BaseSettings):
    zmq_tcp: ZMQTCPConfig | None = None
    zmq_ipc: ZMQIPCConfig | None = None
    _comm_config: BaseZMQCommunicationConfig | None = None

    @model_validator(mode="after")
    def validate_comm_config(self) -> Self:
        """Initialize comm_config based on zmq_tcp or zmq_ipc."""
        if self.zmq_tcp is not None and self.zmq_ipc is not None:
            raise ValueError(
                "Cannot use both ZMQ TCP and ZMQ IPC configuration"
            )
        elif self.zmq_tcp is not None:
            self._comm_config = self.zmq_tcp
        elif self.zmq_ipc is not None:
            self._comm_config = self.zmq_ipc
        else:
            self._comm_config = ZMQIPCConfig()
        return self
```

**Key Features**:
1. Validates mutual exclusivity (can't use both TCP and IPC)
2. Sets default if neither is provided
3. Populates derived field (`_comm_config`)

## Custom Validators

### Field Validator Decorator

Define custom field validators:

```python
from pydantic import field_validator

class EndpointConfig(BaseConfig):
    endpoint_url: str = "http://localhost:8000"

    @field_validator("endpoint_url")
    def validate_endpoint_url(cls, v: str) -> str:
        """Validate endpoint URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Endpoint URL must start with http:// or https://")

        # Remove trailing slash
        return v.rstrip("/")
```

### Multi-Field Validators

Validate multiple fields with a single validator:

```python
from pydantic import field_validator

class LoadConfig(BaseConfig):
    request_rate: float | None = None
    num_requests: int | None = None
    duration: float | None = None

    @field_validator("request_rate", "duration")
    def validate_positive(cls, v: float | None) -> float | None:
        """Ensure numeric values are positive."""
        if v is not None and v <= 0:
            raise ValueError("Value must be positive")
        return v
```

### Validator with Info Parameter

Access field name and other metadata:

```python
from pydantic import field_validator
from pydantic_core import ValidationInfo

class Config(BaseConfig):
    min_value: int = 0
    max_value: int = 100

    @field_validator("min_value", "max_value")
    def validate_range(cls, v: int, info: ValidationInfo) -> int:
        """Validate that value is within expected range."""
        field_name = info.field_name
        if v < 0:
            raise ValueError(f"{field_name} must be non-negative")
        if v > 1000:
            raise ValueError(f"{field_name} must not exceed 1000")
        return v
```

### Chained Validators

Chain multiple validators for the same field:

```python
from pydantic import field_validator

class TextConfig(BaseConfig):
    prompt: str = ""

    @field_validator("prompt")
    def strip_whitespace(cls, v: str) -> str:
        """Remove leading/trailing whitespace."""
        return v.strip()

    @field_validator("prompt")
    def validate_not_empty(cls, v: str) -> str:
        """Ensure prompt is not empty after stripping."""
        if not v:
            raise ValueError("Prompt cannot be empty")
        return v

    @field_validator("prompt")
    def validate_length(cls, v: str) -> str:
        """Ensure prompt is within length limits."""
        if len(v) > 10000:
            raise ValueError("Prompt exceeds maximum length of 10000 characters")
        return v
```

## Validator Utilities

### String or List Parser

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/config_validators.py`:

```python
def parse_str_or_list(input: Any) -> list[Any]:
    """Parse input as string or list.

    Splits strings by commas and trims whitespace.

    Examples:
        "a,b,c" -> ["a", "b", "c"]
        ["a", "b", "c"] -> ["a", "b", "c"]
        ["a,b", "c"] -> ["a", "b", "c"]
    """
    if isinstance(input, str):
        output = [item.strip() for item in input.split(",")]
    elif isinstance(input, list):
        output = []
        for item in input:
            if isinstance(item, str):
                output.extend([token.strip() for token in item.split(",")])
            else:
                output.append(item)
    else:
        raise ValueError(f"Input must be a string or list, got {type(input)}")

    return output
```

**Usage**:

```python
from pydantic import field_validator
from aiperf.common.config.config_validators import parse_str_or_list

class Config(BaseConfig):
    model_names: list[str] = Field(default_factory=list)

    @field_validator("model_names", mode="before")
    def parse_model_names(cls, v: Any) -> list[str]:
        return parse_str_or_list(v)
```

### CSV List Parser

Parse comma-separated values within list items:

```python
def parse_str_or_csv_list(input: Any) -> list[Any]:
    """Parse input as string or CSV list.

    Examples:
        [1, 2, 3] -> [1, 2, 3]
        "1,2,3" -> ["1", "2", "3"]
        ["1,2,3", "4,5,6"] -> ["1", "2", "3", "4", "5", "6"]
        ["1,2,3", 4, 5] -> ["1", "2", "3", 4, 5]
    """
    if isinstance(input, str):
        output = [item.strip() for item in input.split(",")]
    elif isinstance(input, list):
        output = []
        for item in input:
            if isinstance(item, str):
                output.extend([token.strip() for token in item.split(",")])
            else:
                output.append(item)
    else:
        raise ValueError(f"Input must be a string or list")

    return output
```

### Positive Values Parser

Parse and validate positive numeric values:

```python
def parse_str_or_list_of_positive_values(input: Any) -> list[int | float]:
    """Parse input as list of positive numbers.

    Raises:
        ValueError: If any value is not positive
    """
    output = parse_str_or_list(input)

    try:
        output = [
            float(x) if "." in str(x) or "e" in str(x).lower() else int(x)
            for x in output
        ]
    except ValueError as e:
        raise ValueError(f"All values must be numeric") from e

    if not all(isinstance(x, (int, float)) and x > 0 for x in output):
        raise ValueError(f"All values must be positive numbers")

    return output
```

### Dictionary Parser

Parse string or dictionary as tuple list:

```python
def parse_str_or_dict_as_tuple_list(
    input: Any | None
) -> list[tuple[str, Any]] | None:
    """Parse input as list of (key, value) tuples.

    Examples:
        "key1:val1,key2:val2" -> [("key1", "val1"), ("key2", "val2")]
        {"key1": "val1"} -> [("key1", "val1")]
        '{"key1": "val1"}' -> [("key1", "val1")]
    """
    if input is None:
        return None

    if isinstance(input, list | tuple | set):
        output = []
        for item in input:
            res = parse_str_or_dict_as_tuple_list(item)
            if res is not None:
                output.extend(res)
        return output

    if isinstance(input, dict):
        return [(key, coerce_value(value)) for key, value in input.items()]

    if isinstance(input, str):
        if input.startswith("{"):
            # Parse as JSON
            try:
                data = load_json_str(input)
                return [(key, value) for key, value in data.items()]
            except orjson.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string") from e
        else:
            # Parse as key:value pairs
            return [
                (key.strip(), coerce_value(value.strip()))
                for item in input.split(",")
                for key, value in [item.split(":")]
            ]

    raise ValueError(f"Input must be a valid string, list, or dict")
```

### Value Coercion

Automatically coerce string values to appropriate types:

```python
def coerce_value(value: Any) -> Any:
    """Coerce string value to correct type.

    Examples:
        "true" -> True
        "false" -> False
        "123" -> 123
        "1.5" -> 1.5
        "none" -> None
    """
    if not isinstance(value, str):
        return value

    # Boolean
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # None
    if value.lower() in ("none", "null"):
        return None

    # Integer
    if value.isdigit() and (not value.startswith("0") or value == "0"):
        return int(value)

    # Negative integer
    if (
        value.startswith("-")
        and value[1:].isdigit()
        and (not value.startswith("-0") or value == "-0")
    ):
        return int(value)

    # Float
    if value.count(".") == 1 and (
        value.replace(".", "").isdigit()
        or (value.startswith("-") and value[1:].replace(".", "").isdigit())
    ):
        return float(value)

    return value
```

### File Parser

Validate file paths:

```python
from pathlib import Path

def parse_file(value: str | None) -> Path | None:
    """Parse and validate file path.

    Raises:
        ValueError: If path is not a valid file or directory
    """
    if not value:
        return None

    if not isinstance(value, str):
        raise ValueError(f"Expected a string, got {type(value).__name__}")

    path = Path(value)
    if path.is_file() or path.is_dir():
        return path
    else:
        raise ValueError(f"'{value}' is not a valid file or directory")
```

### Service Type Parser

Parse service types with hyphen-to-underscore conversion:

```python
from aiperf.common.enums import ServiceType

def parse_service_types(input: Any | None) -> set[ServiceType] | None:
    """Parse service types from string or list.

    Replaces hyphens with underscores for user convenience.

    Example:
        "load-gen,worker" -> {ServiceType.LOAD_GEN, ServiceType.WORKER}
    """
    if input is None:
        return None

    return {
        ServiceType(service_type.replace("-", "_"))
        for service_type in parse_str_or_csv_list(input)
    }
```

## Error Handling

### Validation Errors

Pydantic raises `ValidationError` for validation failures:

```python
from pydantic import ValidationError

try:
    config = UserConfig(**data)
except ValidationError as e:
    print(e.errors())
    # [
    #   {
    #     'type': 'missing',
    #     'loc': ('endpoint', 'endpoint_url'),
    #     'msg': 'Field required',
    #     'input': {},
    #   }
    # ]
```

### Custom Error Messages

Provide custom error messages:

```python
from pydantic import field_validator

class Config(BaseConfig):
    request_rate: float = 10.0

    @field_validator("request_rate")
    def validate_request_rate(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(
                f"Request rate must be positive, got {v}. "
                f"Use a value greater than 0 requests per second."
            )
        if v > 10000:
            raise ValueError(
                f"Request rate {v} exceeds maximum of 10000. "
                f"Consider using multiple workers for higher rates."
            )
        return v
```

### Error Context

Include context in error messages:

```python
@field_validator("dataset_path")
def validate_dataset(cls, v: Path, info: ValidationInfo) -> Path:
    """Validate dataset path exists."""
    if not v.exists():
        raise ValueError(
            f"Dataset file not found at {v}. "
            f"Please provide a valid path to a dataset file. "
            f"Field: {info.field_name}"
        )
    return v
```

### Collecting Multiple Errors

Pydantic collects all validation errors:

```python
from pydantic import ValidationError

try:
    config = UserConfig(
        endpoint_url="invalid-url",  # Error 1
        request_rate=-10,            # Error 2
        model_names=[],              # Error 3
    )
except ValidationError as e:
    # All three errors are reported
    for error in e.errors():
        print(f"{error['loc']}: {error['msg']}")
```

### Graceful Degradation

Handle validation errors gracefully:

```python
def load_config_with_fallback(data: dict) -> UserConfig:
    """Load config with fallback to defaults on error."""
    try:
        return UserConfig(**data)
    except ValidationError as e:
        logger.warning(f"Configuration validation failed: {e}")
        logger.info("Using default configuration")
        return UserConfig()
```

## Validation Patterns

### Load Pattern Validation

Ensure exactly one load pattern is specified:

```python
from pydantic import model_validator

class LoadConfig(BaseConfig):
    request_rate: float | None = None
    num_requests: int | None = None
    duration: float | None = None

    @model_validator(mode="after")
    def validate_load_pattern(self) -> Self:
        """Ensure exactly one load pattern is specified."""
        patterns = [
            self.request_rate,
            self.num_requests,
            self.duration,
        ]
        count = sum(p is not None for p in patterns)

        if count == 0:
            raise ValueError(
                "Must specify one of: request_rate, num_requests, or duration"
            )
        if count > 1:
            raise ValueError(
                "Cannot specify multiple load patterns. "
                "Choose one of: request_rate, num_requests, or duration"
            )

        return self
```

### Range Validation

Validate min/max ranges:

```python
from pydantic import model_validator

class Config(BaseConfig):
    min_tokens: int = 10
    max_tokens: int = 100

    @model_validator(mode="after")
    def validate_token_range(self) -> Self:
        """Ensure min_tokens <= max_tokens."""
        if self.min_tokens > self.max_tokens:
            raise ValueError(
                f"min_tokens ({self.min_tokens}) cannot exceed "
                f"max_tokens ({self.max_tokens})"
            )
        return self
```

### Mutual Exclusivity

Validate mutually exclusive options:

```python
@model_validator(mode="after")
def validate_communication(self) -> Self:
    """Ensure only one communication mode is active."""
    if self.zmq_tcp is not None and self.zmq_ipc is not None:
        raise ValueError(
            "Cannot use both TCP and IPC communication. "
            "Specify only one."
        )
    return self
```

### Dependency Validation

Validate field dependencies:

```python
@model_validator(mode="after")
def validate_authentication(self) -> Self:
    """Validate authentication configuration."""
    if self.use_authentication:
        if not self.api_key:
            raise ValueError(
                "api_key is required when use_authentication is True"
            )
        if not self.api_secret:
            raise ValueError(
                "api_secret is required when use_authentication is True"
            )
    return self
```

## Cross-Field Validation

### Model Validator for Cross-Field Logic

```python
from pydantic import model_validator
from typing_extensions import Self

class BenchmarkConfig(BaseConfig):
    warmup_duration: float = 10.0
    benchmark_duration: float = 60.0
    cooldown_duration: float = 10.0

    @model_validator(mode="after")
    def validate_phase_durations(self) -> Self:
        """Validate phase durations are reasonable."""
        total = (
            self.warmup_duration +
            self.benchmark_duration +
            self.cooldown_duration
        )

        if total > 3600:  # 1 hour
            raise ValueError(
                f"Total benchmark duration ({total}s) exceeds 1 hour. "
                f"Consider reducing phase durations."
            )

        if self.benchmark_duration < self.warmup_duration * 2:
            raise ValueError(
                f"Benchmark duration should be at least 2x warmup duration "
                f"for accurate measurements."
            )

        return self
```

### Computed Field Validation

Validate computed or derived fields:

```python
@model_validator(mode="after")
def validate_computed_fields(self) -> Self:
    """Validate computed resource requirements."""
    total_workers = self.worker_count * self.process_count

    if total_workers > 256:
        raise ValueError(
            f"Total workers ({total_workers}) exceeds maximum of 256. "
            f"Reduce worker_count or process_count."
        )

    memory_per_worker = 512  # MB
    total_memory = total_workers * memory_per_worker

    if total_memory > 32768:  # 32 GB
        raise ValueError(
            f"Estimated memory usage ({total_memory}MB) exceeds 32GB. "
            f"Reduce worker count."
        )

    return self
```

## Conditional Validation

### Conditional Field Requirements

```python
from pydantic import model_validator

class EndpointConfig(BaseConfig):
    use_ssl: bool = False
    ssl_cert_path: Path | None = None
    ssl_key_path: Path | None = None

    @model_validator(mode="after")
    def validate_ssl_config(self) -> Self:
        """Validate SSL configuration when enabled."""
        if self.use_ssl:
            if not self.ssl_cert_path:
                raise ValueError(
                    "ssl_cert_path required when use_ssl is True"
                )
            if not self.ssl_key_path:
                raise ValueError(
                    "ssl_key_path required when use_ssl is True"
                )

            # Validate files exist
            if not self.ssl_cert_path.exists():
                raise ValueError(
                    f"SSL certificate not found: {self.ssl_cert_path}"
                )
            if not self.ssl_key_path.exists():
                raise ValueError(
                    f"SSL key not found: {self.ssl_key_path}"
                )

        return self
```

### Mode-Specific Validation

```python
@model_validator(mode="after")
def validate_mode_config(self) -> Self:
    """Validate configuration based on execution mode."""
    if self.mode == ExecutionMode.DISTRIBUTED:
        if not self.coordinator_url:
            raise ValueError(
                "coordinator_url required for distributed mode"
            )
        if self.worker_count < 2:
            raise ValueError(
                "distributed mode requires at least 2 workers"
            )
    elif self.mode == ExecutionMode.SINGLE_PROCESS:
        if self.worker_count != 1:
            raise ValueError(
                "single_process mode requires exactly 1 worker"
            )

    return self
```

## Validation Testing

### Testing Field Validation

```python
import pytest
from pydantic import ValidationError

def test_request_rate_validation():
    """Test request rate validation."""
    # Valid values
    config = LoadConfig(request_rate=10.0)
    assert config.request_rate == 10.0

    # Invalid: negative
    with pytest.raises(ValidationError) as exc:
        LoadConfig(request_rate=-10.0)
    assert "greater than or equal to 0" in str(exc.value)

    # Invalid: too high
    with pytest.raises(ValidationError) as exc:
        LoadConfig(request_rate=20000)
    assert "less than or equal to 10000" in str(exc.value)
```

### Testing Model Validation

```python
def test_load_pattern_validation():
    """Test load pattern mutual exclusivity."""
    # Valid: exactly one pattern
    config = LoadConfig(request_rate=10.0)
    assert config.request_rate == 10.0

    # Invalid: multiple patterns
    with pytest.raises(ValidationError) as exc:
        LoadConfig(request_rate=10.0, num_requests=100)
    assert "Cannot specify multiple load patterns" in str(exc.value)

    # Invalid: no patterns
    with pytest.raises(ValidationError) as exc:
        LoadConfig()
    assert "Must specify one of" in str(exc.value)
```

### Testing Custom Validators

```python
def test_endpoint_url_validation():
    """Test custom endpoint URL validator."""
    # Valid URLs
    config = EndpointConfig(endpoint_url="http://localhost:8000")
    assert config.endpoint_url == "http://localhost:8000"

    config = EndpointConfig(endpoint_url="https://api.example.com/")
    assert config.endpoint_url == "https://api.example.com"  # trailing slash removed

    # Invalid: missing protocol
    with pytest.raises(ValidationError) as exc:
        EndpointConfig(endpoint_url="localhost:8000")
    assert "must start with http://" in str(exc.value)
```

### Testing Validation Utilities

```python
from aiperf.common.config.config_validators import parse_str_or_list

def test_parse_str_or_list():
    """Test string/list parser."""
    # String input
    result = parse_str_or_list("a,b,c")
    assert result == ["a", "b", "c"]

    # List input
    result = parse_str_or_list(["a", "b", "c"])
    assert result == ["a", "b", "c"]

    # Mixed CSV list
    result = parse_str_or_list(["a,b", "c"])
    assert result == ["a", "b", "c"]

    # Invalid input
    with pytest.raises(ValueError):
        parse_str_or_list(123)
```

## Best Practices

### 1. Use Type Hints

Always provide complete type hints:

```python
# Good
request_rate: float = 10.0

# Better
request_rate: Annotated[
    float,
    Field(ge=0, le=10000, description="Requests per second")
] = 10.0
```

### 2. Provide Descriptive Error Messages

```python
# Good
if v <= 0:
    raise ValueError("Must be positive")

# Better
if v <= 0:
    raise ValueError(
        f"Request rate must be positive, got {v}. "
        f"Use a value greater than 0 requests per second."
    )
```

### 3. Validate Early

Validate at the earliest possible point:

```python
# Validate at field level when possible
request_rate: Annotated[float, Field(ge=0)] = 10.0

# Use model validators for cross-field logic
@model_validator(mode="after")
def validate_cross_fields(self) -> Self:
    # Cross-field validation here
    return self
```

### 4. Use Before Validators for Parsing

```python
# Use before validators for data transformation
@field_validator("model_names", mode="before")
def parse_model_names(cls, v: Any) -> list[str]:
    return parse_str_or_list(v)

# Use after validators for business logic
@model_validator(mode="after")
def validate_model_count(self) -> Self:
    if len(self.model_names) > 5:
        raise ValueError("Maximum 5 models allowed")
    return self
```

### 5. Test Validation Logic

```python
def test_validation():
    """Always test validation logic."""
    # Test valid cases
    config = Config(value=10)

    # Test edge cases
    config = Config(value=0)
    config = Config(value=100)

    # Test invalid cases
    with pytest.raises(ValidationError):
        Config(value=-1)
```

### 6. Document Validation Rules

```python
class Config(BaseConfig):
    """Configuration with validated fields.

    Validation Rules:
        - request_rate: Must be between 0 and 10000
        - model_names: Must contain 1-5 model names
        - timeout: Must be positive if specified
    """
    request_rate: float = Field(ge=0, le=10000)
    model_names: list[str] = Field(min_length=1, max_length=5)
    timeout: float | None = Field(default=None, gt=0)
```

### 7. Reuse Validation Logic

```python
# Extract common validation patterns
def validate_positive_numeric(v: float, field_name: str) -> float:
    """Reusable positive number validator."""
    if v <= 0:
        raise ValueError(f"{field_name} must be positive")
    return v

class Config(BaseConfig):
    @field_validator("request_rate")
    def validate_request_rate(cls, v: float) -> float:
        return validate_positive_numeric(v, "request_rate")

    @field_validator("timeout")
    def validate_timeout(cls, v: float) -> float:
        return validate_positive_numeric(v, "timeout")
```

## Key Takeaways

1. **Multi-Layer Validation**: AIPerf uses field validators, model validators, and runtime checks for comprehensive validation.

2. **Pydantic Foundation**: Built on Pydantic's powerful validation framework with type safety and constraint checking.

3. **Before/After Validators**: Use before validators for parsing, after validators for business logic.

4. **Validation Utilities**: Reusable utilities in `config_validators.py` handle common parsing patterns.

5. **Clear Error Messages**: Validation errors provide actionable feedback to users.

6. **Cross-Field Validation**: Model validators enable complex validation across multiple fields.

7. **Conditional Validation**: Support for mode-specific and conditional validation logic.

8. **Testing Critical**: All validation logic should be thoroughly tested.

9. **Early Validation**: Validate at the earliest point to catch errors quickly.

10. **Reusable Patterns**: Extract common validation patterns for consistency.

11. **Type Safety**: Full type annotations enable IDE support and catch errors early.

12. **Documentation**: Document validation rules clearly in docstrings.

## Navigation

- Previous: [Chapter 32: CLI Integration](chapter-32-cli-integration.md)
- Next: [Chapter 34: UI Architecture](chapter-34-ui-architecture.md)
- [Back to Index](INDEX.md)
