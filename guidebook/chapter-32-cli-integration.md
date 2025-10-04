<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 32: CLI Integration

## Overview

AIPerf's command-line interface is built on Cyclopts, a modern Python CLI framework that automatically generates commands from function signatures and type annotations. This chapter explores the complete CLI integration architecture, from parameter mapping to help generation, providing developers with a comprehensive understanding of how AIPerf exposes its configuration system through the command line.

The CLI system is designed for simplicity and performance, with minimal imports at the top level to ensure fast startup times, even for simple help commands. It seamlessly integrates with Pydantic configuration models to provide type-safe, well-documented command-line interfaces.

## Table of Contents

1. [CLI Architecture](#cli-architecture)
2. [Cyclopts Integration](#cyclopts-integration)
3. [Parameter Mapping](#parameter-mapping)
4. [Command Structure](#command-structure)
5. [CLI Parameter Configuration](#cli-parameter-configuration)
6. [Help Generation](#help-generation)
7. [CLI Groups](#cli-groups)
8. [Type Conversion](#type-conversion)
9. [Validation Integration](#validation-integration)
10. [Error Handling](#error-handling)
11. [Advanced CLI Patterns](#advanced-cli-patterns)
12. [Testing CLI Commands](#testing-cli-commands)

## CLI Architecture

### Entry Point

The CLI entry point is defined in `/home/anthony/nvidia/projects/aiperf/aiperf/cli.py`:

```python
"""Main CLI entry point for the AIPerf system."""

# NOTE: Keep the imports here to a minimum. This file is read every time
# the CLI is run, including to generate the help text. Any imports here
# will cause a performance penalty during this process.

import sys
from cyclopts import App

from aiperf.cli_utils import exit_on_error
from aiperf.common.config import ServiceConfig, UserConfig

app = App(name="aiperf", help="NVIDIA AIPerf")

@app.command(name="profile")
def profile(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
) -> None:
    """Run the Profile subcommand.

    Args:
        user_config: User configuration for the benchmark
        service_config: Service configuration options
    """
    with exit_on_error(title="Error Running AIPerf System"):
        from aiperf.cli_runner import run_system_controller
        from aiperf.common.config import load_service_config

        service_config = service_config or load_service_config()

        run_system_controller(user_config, service_config)

if __name__ == "__main__":
    sys.exit(app())
```

### Design Principles

1. **Minimal Imports**: Only essential imports at module level for fast help text generation
2. **Lazy Loading**: Heavy imports deferred until command execution
3. **Type-Driven**: CLI parameters automatically derived from type annotations
4. **Error Handling**: Comprehensive error handling with rich formatting
5. **Pydantic Integration**: Direct mapping from Pydantic models to CLI parameters

### Performance Optimization

The comment at the top of `cli.py` highlights the performance-first design:

```python
# NOTE: Keep the imports here to a minimum. This file is read every time
# the CLI is run, including to generate the help text. Any imports here
# will cause a performance penalty during this process.
```

This ensures that running `aiperf --help` is instantaneous, even though AIPerf has many dependencies.

## Cyclopts Integration

### App Creation

Cyclopts App is the root of the CLI hierarchy:

```python
from cyclopts import App

app = App(name="aiperf", help="NVIDIA AIPerf")
```

**Parameters**:
- `name`: CLI program name (appears in help text)
- `help`: Top-level help description

### Command Registration

Commands are registered using the `@app.command()` decorator:

```python
@app.command(name="profile")
def profile(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
) -> None:
    """Run the Profile subcommand."""
    # Command implementation
```

### Automatic Parameter Detection

Cyclopts automatically converts function parameters to CLI arguments based on:

1. **Parameter name**: Becomes the CLI flag name
2. **Type annotation**: Determines parsing and validation
3. **Default value**: Makes the parameter optional
4. **Docstring**: Extracted for help text

### Pydantic Model Integration

When a parameter is typed as a Pydantic model, Cyclopts introspects the model and exposes all fields as CLI parameters:

```python
def profile(
    user_config: UserConfig,  # All UserConfig fields become CLI parameters
    service_config: ServiceConfig | None = None,  # Optional
) -> None:
    ...
```

This automatic expansion enables the entire AIPerf configuration to be controlled via CLI.

### Cyclopts Features Used

AIPerf leverages these Cyclopts features:

1. **Automatic Help Generation**: From docstrings and field descriptions
2. **Type Coercion**: Automatic conversion from strings to typed values
3. **Nested Configuration**: Support for nested Pydantic models
4. **Parameter Groups**: Organized help output
5. **Custom Converters**: For enum types and special parsing

## Parameter Mapping

### CLI Parameter Class

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/cli_parameter.py`:

```python
from cyclopts import Parameter

class CLIParameter(Parameter):
    """Configuration for a CLI parameter.

    This is a subclass of the cyclopts.Parameter class that includes
    the default configuration AIPerf uses for all of its CLI parameters.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, show_env_var=False, negative=False, **kwargs)
```

**Default Configuration**:
- `show_env_var=False`: Environment variables not shown in help (to reduce clutter)
- `negative=False`: No automatic `--no-` flag generation for booleans

### Field Annotation Pattern

AIPerf uses a consistent annotation pattern for CLI-enabled fields:

```python
from typing import Annotated
from pydantic import Field

log_level: Annotated[
    AIPerfLogLevel,                          # Type
    Field(description="Logging level"),      # Pydantic field
    CLIParameter(                            # CLI configuration
        name=("--log-level"),
        group=Groups.SERVICE,
    ),
] = ServiceDefaults.LOG_LEVEL               # Default value
```

**Components**:
1. **Type**: The Python type for the field
2. **Field**: Pydantic Field with description and validation
3. **CLIParameter**: CLI-specific configuration
4. **Default**: Default value from defaults module

### Parameter Name Mapping

CLI parameter names are explicitly defined:

```python
CLIParameter(
    name=("--log-level"),  # Single name
)

CLIParameter(
    name=("--verbose", "-v"),  # Long and short form
)

CLIParameter(
    name=("--record-processor-service-count", "--record-processors"),  # Aliases
)
```

### Disabling CLI Parameters

Some fields should not be exposed via CLI:

```python
class DisableCLI(CLIParameter):
    """Configuration for a CLI parameter that is disabled."""

    def __init__(self, reason: str = "Not supported via command line", *args, **kwargs):
        super().__init__(*args, parse=False, **kwargs)
```

**Usage**:

```python
service_run_type: Annotated[
    ServiceRunType,
    Field(description="Type of service run (process, k8s)"),
    DisableCLI(reason="Only single support for now"),
] = ServiceDefaults.SERVICE_RUN_TYPE
```

Setting `parse=False` tells Cyclopts to skip this field entirely.

### Developer-Only Parameters

Parameters only available when developer mode is enabled:

```python
from aiperf.common.constants import AIPERF_DEV_MODE

class DeveloperOnlyCLI(CLIParameter):
    """Configuration for a CLI parameter that is only available to developers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, parse=AIPERF_DEV_MODE, group=Groups.DEVELOPER, **kwargs)
```

**Behavior**:
- If `AIPERF_DEV_MODE` environment variable is set, parameter is available
- Otherwise, parameter is hidden and disabled

## Command Structure

### Profile Command

The primary AIPerf command:

```python
@app.command(name="profile")
def profile(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
) -> None:
    """Run the Profile subcommand.

    Args:
        user_config: User configuration for the benchmark
        service_config: Service configuration options
    """
    with exit_on_error(title="Error Running AIPerf System"):
        from aiperf.cli_runner import run_system_controller
        from aiperf.common.config import load_service_config

        service_config = service_config or load_service_config()
        run_system_controller(user_config, service_config)
```

**Key Features**:

1. **Lazy Import**: Heavy imports inside function for fast help
2. **Error Context**: `exit_on_error` provides rich error messages
3. **Default Loading**: `service_config` has intelligent defaults
4. **Type Safety**: Full type annotations for IDE support

### Command Execution Flow

1. User runs: `aiperf profile --endpoint-url http://localhost:8000 config.yaml`
2. Cyclopts parses arguments and maps to `UserConfig` and `ServiceConfig`
3. Pydantic validates and constructs config objects
4. `profile()` function is called with validated configs
5. Lazy imports load heavy modules
6. `run_system_controller()` executes the benchmark

### CLI Runner

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/cli_runner.py`, the runner orchestrates system startup:

```python
def run_system_controller(
    user_config: UserConfig,
    service_config: ServiceConfig,
) -> None:
    """Run the system controller with the provided configuration."""

    # Setup logging
    setup_rich_logging(user_config, service_config)

    # Create controller
    controller = SystemController(
        user_config=user_config,
        service_config=service_config,
    )

    # Run benchmark
    asyncio.run(controller.run())
```

## CLI Parameter Configuration

### Configuration Groups

Parameters are organized into logical groups:

```python
from aiperf.common.config.groups import Groups

class Groups:
    """CLI parameter groups for organized help output."""

    ENDPOINT = "Endpoint Configuration"
    INPUT = "Input Configuration"
    OUTPUT = "Output Configuration"
    SERVICE = "Service Configuration"
    LOAD = "Load Configuration"
    DEVELOPER = "Developer Options"
```

**Purpose**: Groups organize the help output, making it easier to find related parameters.

### Group Assignment

Assign parameters to groups:

```python
log_level: Annotated[
    AIPerfLogLevel,
    Field(description="Logging level"),
    CLIParameter(
        name=("--log-level"),
        group=Groups.SERVICE,  # Appears under "Service Configuration"
    ),
] = ServiceDefaults.LOG_LEVEL
```

### Parameter Visibility

Control parameter visibility in help:

```python
# Always visible
CLIParameter(name="--visible-param")

# Hidden from help but still functional
CLIParameter(name="--hidden-param", hidden=True)

# Completely disabled
DisableCLI(reason="Not supported")

# Developer-only
DeveloperOnlyCLI()
```

### Parameter Metadata

Additional metadata for CLI parameters:

```python
CLIParameter(
    name=("--parameter-name", "-p"),
    group=Groups.INPUT,
    show=True,                    # Show in help
    show_default=True,            # Show default value
    show_env_var=False,           # Hide env var name
    negative=False,               # No --no- flag for bools
)
```

## Help Generation

### Automatic Help Text

Help text is automatically generated from:

1. **Function docstring**: Command description
2. **Field descriptions**: Parameter descriptions
3. **Default values**: Displayed in help
4. **Type annotations**: Used to generate type hints

### Help Output Example

Running `aiperf profile --help` produces:

```
Usage: aiperf profile [OPTIONS] CONFIG_FILE

Run the Profile subcommand.

Arguments:
  CONFIG_FILE    Path to configuration file

Endpoint Configuration:
  --endpoint-url URL         API endpoint URL
  --model-names MODELS       Model names (comma-separated)

Service Configuration:
  --log-level LEVEL          Logging level [default: INFO]
  --verbose, -v              Enable verbose logging
  --extra-verbose, -vv       Enable trace logging
  --ui-type TYPE             UI type [default: tqdm]

Output Configuration:
  --artifact-directory DIR   Output directory [default: artifacts]
  --export-formats FORMATS   Export formats [default: json,csv]

Load Configuration:
  --request-rate RATE        Requests per second
  --duration SECONDS         Benchmark duration

Developer Options:
  (Only visible with AIPERF_DEV_MODE=1)
```

### Custom Help Sections

Add custom help sections using docstrings:

```python
@app.command(name="profile")
def profile(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
) -> None:
    """Run the Profile subcommand.

    This command executes a performance profiling benchmark against
    the specified endpoint. It supports various load patterns and
    generates detailed performance metrics.

    Examples:
        Basic usage:
            aiperf profile config.yaml

        With verbose logging:
            aiperf profile -v config.yaml

        Custom request rate:
            aiperf profile --request-rate 100 config.yaml

    Args:
        user_config: User configuration for the benchmark
        service_config: Service configuration options
    """
```

### Help Text Best Practices

1. **Concise Descriptions**: Keep field descriptions to one line when possible
2. **Document Defaults**: Always show default values
3. **Provide Examples**: Include usage examples in command docstrings
4. **Organize Logically**: Use groups to organize related parameters
5. **Type Information**: Leverage type annotations for automatic help

## CLI Groups

### Defining Groups

Groups are defined in `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/groups.py`:

```python
class Groups:
    """CLI parameter groups for organized help output."""

    ENDPOINT = "Endpoint Configuration"
    INPUT = "Input Configuration"
    OUTPUT = "Output Configuration"
    PROMPT = "Prompt Configuration"
    IMAGE = "Image Configuration"
    AUDIO = "Audio Configuration"
    SERVICE = "Service Configuration"
    LOAD = "Load Configuration"
    TIMING = "Timing Configuration"
    DEVELOPER = "Developer Options"
```

### Group Usage

Apply groups to parameters:

```python
# Endpoint configuration field
endpoint_url: Annotated[
    str,
    Field(description="API endpoint URL"),
    CLIParameter(name="--endpoint-url", group=Groups.ENDPOINT),
]

# Service configuration field
log_level: Annotated[
    AIPerfLogLevel,
    Field(description="Logging level"),
    CLIParameter(name="--log-level", group=Groups.SERVICE),
]
```

### Group Organization Benefits

1. **Logical Grouping**: Related parameters appear together in help
2. **Easier Navigation**: Users can quickly find parameters
3. **Reduced Cognitive Load**: Organized help is easier to understand
4. **Scalability**: Easy to add new parameters without help clutter

### Group Ordering

Cyclopts displays groups in the order they first appear in the configuration models. To control ordering, define groups in a specific order in your base configuration.

## Type Conversion

### Automatic Type Conversion

Cyclopts automatically converts string arguments to typed values:

```python
# Integer
request_rate: int = 10
# CLI: --request-rate 100

# Float
duration: float = 60.0
# CLI: --duration 30.5

# Boolean
verbose: bool = False
# CLI: --verbose

# String
model_name: str = "gpt-4"
# CLI: --model-name "gpt-4"
```

### Enum Conversion

AIPerf uses custom enum conversion for case-insensitive enums:

```python
from aiperf.common.config.config_validators import custom_enum_converter

def custom_enum_converter(type_: Any, value: Sequence[Token]) -> Any:
    """Custom converter for cyclopts that allows us to use our custom enum types."""
    if len(value) != 1:
        raise ValueError(f"Expected 1 value, but got {len(value)}")
    return type_(value[0].value)
```

**Usage with Cyclopts**:

```python
from cyclopts import App
from aiperf.common.enums import AIPerfLogLevel

app = App(
    name="aiperf",
    converter={AIPerfLogLevel: custom_enum_converter}
)
```

This enables case-insensitive enum parsing:

```bash
# All of these work:
aiperf profile --log-level DEBUG
aiperf profile --log-level debug
aiperf profile --log-level Debug
```

### List Conversion

Lists are parsed from comma-separated strings:

```python
from aiperf.common.config.config_validators import parse_str_or_list

model_names: list[str] = Field(default_factory=list)
# CLI: --model-names model1,model2,model3

# Validator handles conversion
@field_validator("model_names", mode="before")
def parse_model_names(cls, value):
    return parse_str_or_list(value)
```

### Dictionary Conversion

Dictionaries are parsed from key:value pairs:

```python
from aiperf.common.config.config_validators import parse_str_or_dict_as_tuple_list

headers: dict[str, str] = {}
# CLI: --headers "key1:value1,key2:value2"
# Or: --headers '{"key1": "value1", "key2": "value2"}'

@field_validator("headers", mode="before")
def parse_headers(cls, value):
    result = parse_str_or_dict_as_tuple_list(value)
    return dict(result) if result else {}
```

### Path Conversion

Paths are validated and converted:

```python
from pathlib import Path
from aiperf.common.config.config_validators import parse_file

config_file: Path | None = None
# CLI: --config-file /path/to/config.yaml

@field_validator("config_file", mode="before")
def parse_config_file(cls, value):
    return parse_file(value)
```

### Custom Type Converters

Define custom converters for complex types:

```python
from cyclopts.token import Token

def custom_type_converter(type_: type, value: Sequence[Token]) -> Any:
    """Custom converter for a specialized type."""
    if len(value) != 1:
        raise ValueError("Expected single value")

    # Custom parsing logic
    return type_.from_string(value[0].value)

# Register with Cyclopts
app = App(
    name="aiperf",
    converter={CustomType: custom_type_converter}
)
```

## Validation Integration

### Pydantic Validation

All CLI parameters go through Pydantic validation:

```python
from pydantic import Field, field_validator

class MyConfig(BaseConfig):
    request_rate: Annotated[
        float,
        Field(ge=0, le=10000, description="Requests per second"),
        CLIParameter(name="--request-rate"),
    ] = 10.0

    @field_validator("request_rate")
    def validate_request_rate(cls, v):
        if v > 1000:
            warnings.warn("Very high request rate may overwhelm the system")
        return v
```

**CLI Validation Flow**:
1. Cyclopts parses string to Python type
2. Pydantic applies Field validators (ge, le, etc.)
3. Custom field validators execute
4. Model validators execute
5. Validated config object returned

### Field Constraints

Pydantic Field constraints are enforced:

```python
# Numeric constraints
request_rate: Annotated[
    float,
    Field(ge=0, le=10000),  # Greater than or equal to 0, less than or equal to 10000
]

# String constraints
model_name: Annotated[
    str,
    Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9-_]+$"),
]

# List constraints
model_names: Annotated[
    list[str],
    Field(min_length=1, max_length=10),  # List must have 1-10 items
]
```

### Cross-Field Validation

Model validators enable cross-field validation:

```python
from pydantic import model_validator

class LoadConfig(BaseConfig):
    request_rate: float | None = None
    num_requests: int | None = None
    duration: float | None = None

    @model_validator(mode="after")
    def validate_load_pattern(self) -> Self:
        """Ensure a valid load pattern is specified."""
        patterns = [self.request_rate, self.num_requests, self.duration]
        if sum(p is not None for p in patterns) != 1:
            raise ValueError(
                "Exactly one of request_rate, num_requests, or duration must be specified"
            )
        return self
```

### Validation Error Messages

Pydantic provides clear error messages for validation failures:

```bash
$ aiperf profile --request-rate -10 config.yaml

Error: Validation Error

user_config.load.request_rate
  Input should be greater than or equal to 0
  [type=greater_than_equal, input_value=-10]
```

## Error Handling

### Exit on Error Context Manager

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/cli_utils.py`:

```python
from contextlib import AbstractContextManager
from rich.console import Console
from rich.panel import Panel

class exit_on_error(AbstractContextManager):
    """Context manager that exits the program if an error occurs."""

    def __init__(
        self,
        *exceptions: type[BaseException],
        message: "RenderableType" = "{e}",
        text_color: "StyleType | None" = None,
        title: str = "Error",
        exit_code: int = 1,
    ):
        self.message = message
        self.text_color = text_color
        self.title = title
        self.exit_code = exit_code
        self.exceptions = exceptions

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return

        if (
            not self.exceptions
            and not isinstance(exc_value, (SystemExit | KeyboardInterrupt))
        ) or issubclass(exc_type, self.exceptions):
            console = Console()
            console.print_exception(
                show_locals=True,
                max_frames=10,
                word_wrap=True,
                width=console.width,
            )
            console.file.flush()
            message = (
                self.message.format(e=exc_value)
                if isinstance(self.message, str)
                else self.message
            )
            raise_startup_error_and_exit(
                message,
                text_color=self.text_color,
                title=self.title,
                exit_code=self.exit_code,
            )
```

**Usage**:

```python
@app.command(name="profile")
def profile(user_config: UserConfig, service_config: ServiceConfig | None = None):
    with exit_on_error(title="Error Running AIPerf System"):
        # Command implementation
        run_system_controller(user_config, service_config)
```

**Features**:
1. Catches exceptions and displays rich error messages
2. Shows full stack trace with local variables
3. Formats errors in a panel for visibility
4. Exits with appropriate exit code

### Error Display Function

```python
def raise_startup_error_and_exit(
    message: "RenderableType",
    text_color: "StyleType | None" = None,
    title: str = "Error",
    exit_code: int = 1,
    border_style: "StyleType" = "bold red",
    title_align: "AlignMethod" = "left",
) -> None:
    """Raise a startup error and exit the program."""
    console = Console()
    console.print(
        Panel(
            renderable=message,
            title=title,
            title_align=title_align,
            border_style=border_style,
        )
    )
    sys.exit(exit_code)
```

**Error Display Example**:

```
┌─ Error Running AIPerf System ───────────────────────────────┐
│                                                              │
│ ValidationError: 1 validation error for UserConfig          │
│ endpoint.endpoint_url                                        │
│   Field required [type=missing, input_value={}]             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Specific Error Handlers

Handle specific error types:

```python
with exit_on_error(
    ValueError,
    FileNotFoundError,
    title="Configuration Error",
    message="Invalid configuration: {e}"
):
    # Code that may raise specific exceptions
```

### User-Friendly Error Messages

Convert technical errors to user-friendly messages:

```python
try:
    config = UserConfig(**config_dict)
except ValidationError as e:
    # Extract specific field errors
    errors = e.errors()
    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"])
        msg = error["msg"]
        print(f"Configuration error in {field}: {msg}")
    sys.exit(1)
```

## Advanced CLI Patterns

### Configuration File Support

AIPerf supports loading configuration from files:

```bash
# YAML configuration file
aiperf profile config.yaml

# JSON configuration file
aiperf profile config.json
```

The file is passed as a positional argument and loaded by UserConfig:

```python
from pathlib import Path
from ruamel.yaml import YAML

class UserConfig(BaseConfig):
    @classmethod
    def from_file(cls, path: Path) -> "UserConfig":
        """Load configuration from file."""
        yaml = YAML(pure=True)
        with open(path) as f:
            data = yaml.load(f)
        return cls(**data)
```

### CLI Overrides

CLI parameters override file configuration:

```bash
# Load from file but override specific values
aiperf profile config.yaml --request-rate 100 --verbose
```

Cyclopts merges file and CLI configurations with CLI taking precedence.

### Environment Variable Integration

Configuration precedence:

1. CLI parameters (highest)
2. Environment variables
3. Configuration file
4. Default values (lowest)

```bash
# Set via environment
export AIPERF_LOG_LEVEL=DEBUG

# Override with CLI
aiperf profile config.yaml --log-level INFO  # INFO is used
```

### Subcommand Pattern

Define multiple subcommands:

```python
app = App(name="aiperf", help="NVIDIA AIPerf")

@app.command(name="profile")
def profile(user_config: UserConfig, service_config: ServiceConfig | None = None):
    """Run a performance profile."""
    pass

@app.command(name="analyze")
def analyze(results_file: Path):
    """Analyze benchmark results."""
    pass

@app.command(name="compare")
def compare(file1: Path, file2: Path):
    """Compare two benchmark results."""
    pass
```

Usage:

```bash
aiperf profile config.yaml
aiperf analyze results.json
aiperf compare run1.json run2.json
```

### Configuration Validation Command

Add a command to validate configuration without running:

```python
@app.command(name="validate")
def validate(user_config: UserConfig, service_config: ServiceConfig | None = None):
    """Validate configuration without running benchmark."""
    service_config = service_config or load_service_config()

    console = Console()
    console.print("[green]Configuration is valid![/green]")
    console.print(f"Model: {user_config.endpoint.model_names[0]}")
    console.print(f"Endpoint: {user_config.endpoint.endpoint_url}")
    console.print(f"Request Rate: {user_config.load.request_rate}")
```

### Template Generation Command

Generate configuration templates:

```python
@app.command(name="template")
def template(output: Path, verbose: bool = False):
    """Generate a configuration template."""
    config = UserConfig()
    yaml_content = config.serialize_to_yaml(verbose=verbose)

    with open(output, "w") as f:
        f.write(yaml_content)

    console = Console()
    console.print(f"[green]Template written to {output}[/green]")
```

Usage:

```bash
aiperf template config.yaml
aiperf template --verbose config-detailed.yaml
```

## Testing CLI Commands

### Test Configuration

Create test configurations:

```python
import pytest
from aiperf.common.config import UserConfig, ServiceConfig

@pytest.fixture
def test_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            endpoint_url="http://localhost:8000",
            model_names=["test-model"],
        ),
        load=LoadConfig(request_rate=10),
    )

@pytest.fixture
def test_service_config():
    return ServiceConfig(
        log_level=AIPerfLogLevel.DEBUG,
        ui_type=AIPerfUIType.NO_UI,
    )
```

### CLI Invocation Testing

Test CLI commands programmatically:

```python
from cyclopts.testing import runner

def test_profile_command():
    """Test the profile command."""
    result = runner.invoke(
        app,
        ["profile", "test-config.yaml", "--verbose"]
    )

    assert result.exit_code == 0
    assert "Starting benchmark" in result.output
```

### Argument Parsing Testing

Test argument parsing:

```python
def test_request_rate_parsing():
    """Test request rate parameter parsing."""
    result = runner.invoke(
        app,
        ["profile", "config.yaml", "--request-rate", "100"]
    )

    # Verify parsing succeeded
    assert result.exit_code == 0
```

### Validation Error Testing

Test validation errors:

```python
def test_invalid_request_rate():
    """Test invalid request rate error."""
    result = runner.invoke(
        app,
        ["profile", "config.yaml", "--request-rate", "-10"]
    )

    assert result.exit_code != 0
    assert "greater than or equal to 0" in result.output
```

### Help Text Testing

Test help text generation:

```python
def test_help_text():
    """Test help text generation."""
    result = runner.invoke(app, ["profile", "--help"])

    assert result.exit_code == 0
    assert "Run the Profile subcommand" in result.output
    assert "--request-rate" in result.output
    assert "--log-level" in result.output
```

### Integration Testing

Test end-to-end CLI workflows:

```python
import tempfile
from pathlib import Path

def test_full_workflow():
    """Test complete workflow from CLI invocation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"

        # Create config file
        config = UserConfig(
            endpoint=EndpointConfig(
                endpoint_url="http://localhost:8000",
                model_names=["test-model"],
            ),
            output=OutputConfig(
                artifact_directory=Path(tmpdir) / "results"
            ),
        )
        config_yaml = config.serialize_to_yaml()
        config_file.write_text(config_yaml)

        # Run CLI command
        result = runner.invoke(
            app,
            ["profile", str(config_file), "--verbose"]
        )

        # Verify results
        assert result.exit_code == 0
        assert (Path(tmpdir) / "results").exists()
```

## Key Takeaways

1. **Cyclopts Integration**: AIPerf uses Cyclopts for automatic CLI generation from Python functions and types.

2. **Performance-Optimized**: Minimal imports at module level ensure fast startup, even for help commands.

3. **Type-Driven**: Type annotations drive CLI parameter generation, validation, and help text.

4. **Pydantic Validation**: All CLI inputs pass through Pydantic validation for type safety and constraint checking.

5. **Rich Error Messages**: The exit_on_error context manager provides formatted, user-friendly error messages.

6. **Parameter Organization**: CLI groups organize parameters logically for better user experience.

7. **Flexible Configuration**: Supports configuration from files, environment variables, and CLI arguments with clear precedence.

8. **Custom Converters**: Enum and complex type conversion is handled by custom converters.

9. **Developer Mode**: Developer-only parameters are conditionally enabled via environment variable.

10. **Extensible Design**: Easy to add new commands and parameters following established patterns.

11. **Test-Friendly**: CLI commands can be tested programmatically using Cyclopts testing utilities.

12. **Help Generation**: Automatic help text generation from docstrings and field descriptions.

## Navigation

- Previous: [Chapter 31: ServiceConfig Deep Dive](chapter-31-serviceconfig-deep-dive.md)
- Next: [Chapter 33: Validation System](chapter-33-validation-system.md)
- [Back to Index](INDEX.md)
