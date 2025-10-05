# Chapter 31: ServiceConfig Deep Dive

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

The `ServiceConfig` class is the cornerstone of AIPerf's service configuration system. It provides a centralized, type-safe, and environment-aware configuration mechanism for all services within the AIPerf ecosystem. This chapter provides an exhaustive exploration of ServiceConfig, covering its architecture, runtime parameters, environment variable integration, and service orchestration capabilities.

ServiceConfig leverages Pydantic Settings for powerful validation and serialization, integrates seamlessly with the CLI system through Cyclopts, and provides sophisticated communication configuration management for distributed service architectures.

## Table of Contents

1. [ServiceConfig Architecture](#serviceconfig-architecture)
2. [Core Components](#core-components)
3. [Runtime Parameters](#runtime-parameters)
4. [Environment Variables](#environment-variables)
5. [Communication Configuration](#communication-configuration)
6. [Service Orchestration](#service-orchestration)
7. [Logging Configuration](#logging-configuration)
8. [Worker Configuration](#worker-configuration)
9. [UI Type Selection](#ui-type-selection)
10. [Developer Configuration](#developer-configuration)
11. [Validation and Lifecycle](#validation-and-lifecycle)
12. [Integration Patterns](#integration-patterns)

## ServiceConfig Architecture

### Class Definition

The ServiceConfig class is located at `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/service_config.py` and provides the base configuration for all AIPerf services.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class ServiceConfig(BaseSettings):
    """Base configuration for all services.

    It will be provided to all services during their __init__ function.
    """

    model_config = SettingsConfigDict(
        env_prefix="AIPERF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )
```

### Key Design Principles

1. **Pydantic Settings Integration**: ServiceConfig extends `BaseSettings`, enabling automatic environment variable parsing and validation.

2. **Environment Prefix**: All environment variables are prefixed with `AIPERF_`, preventing namespace collisions.

3. **Flexible Configuration**: The `extra="allow"` setting permits additional fields, supporting extensibility for custom services.

4. **Type Safety**: All fields are fully typed with Pydantic Field definitions, ensuring compile-time and runtime type safety.

5. **CLI Integration**: Fields are annotated with `CLIParameter` for seamless command-line interface integration.

## Core Components

### Model Configuration

The `model_config` dictionary defines Pydantic Settings behavior:

```python
model_config = SettingsConfigDict(
    env_prefix="AIPERF_",        # All env vars start with AIPERF_
    env_file=".env",             # Load from .env file if present
    env_file_encoding="utf-8",   # UTF-8 encoding for .env files
    extra="allow",               # Allow additional fields for extensibility
)
```

### CLI Group Configuration

ServiceConfig defines a CLI group for organizing command-line parameters:

```python
_CLI_GROUP = Groups.SERVICE
```

This groups all service-related CLI parameters under a common help section, improving user experience.

### Communication Configuration

The private `_comm_config` field stores the active communication configuration:

```python
_comm_config: BaseZMQCommunicationConfig | None = None
```

This is populated during validation based on the `zmq_tcp` or `zmq_ipc` configuration.

## Runtime Parameters

### Service Run Type

Controls how services are executed:

```python
service_run_type: Annotated[
    ServiceRunType,
    Field(
        description="Type of service run (process, k8s)",
    ),
    DisableCLI(reason="Only single support for now"),
] = ServiceDefaults.SERVICE_RUN_TYPE
```

**Default Value**: `ServiceRunType.MULTIPROCESSING`

**Purpose**: Determines the execution model for services. Currently supports:
- `MULTIPROCESSING`: Services run as separate Python processes
- Future support planned for Kubernetes deployments

**CLI Status**: Disabled via `DisableCLI` - not currently user-configurable.

### ZMQ TCP Configuration

Configures TCP-based ZMQ communication:

```python
zmq_tcp: Annotated[
    ZMQTCPConfig | None,
    Field(
        description="ZMQ TCP configuration",
    ),
] = None
```

**Usage Example**:

```python
from aiperf.common.config.zmq_config import ZMQTCPConfig

service_config = ServiceConfig(
    zmq_tcp=ZMQTCPConfig(
        host="127.0.0.1",
        port=5555,
    )
)
```

### ZMQ IPC Configuration

Configures IPC-based ZMQ communication:

```python
zmq_ipc: Annotated[
    ZMQIPCConfig | None,
    Field(
        description="ZMQ IPC configuration",
    ),
] = None
```

**Usage Example**:

```python
from aiperf.common.config.zmq_config import ZMQIPCConfig

service_config = ServiceConfig(
    zmq_ipc=ZMQIPCConfig(
        socket_dir="/tmp/aiperf/sockets",
    )
)
```

**Note**: ZMQ IPC is the default communication mechanism and is automatically configured if neither `zmq_tcp` nor `zmq_ipc` is provided.

## Environment Variables

### Environment Variable Loading

ServiceConfig automatically loads environment variables with the `AIPERF_` prefix. The loading priority is:

1. Explicit constructor arguments (highest priority)
2. Environment variables with `AIPERF_` prefix
3. `.env` file in the current directory
4. Default values defined in ServiceDefaults (lowest priority)

### Environment Variable Naming

Environment variables are derived from field names using uppercase and underscores:

| Field Name | Environment Variable |
|-----------|---------------------|
| `log_level` | `AIPERF_LOG_LEVEL` |
| `verbose` | `AIPERF_VERBOSE` |
| `extra_verbose` | `AIPERF_EXTRA_VERBOSE` |
| `record_processor_service_count` | `AIPERF_RECORD_PROCESSOR_SERVICE_COUNT` |
| `ui_type` | `AIPERF_UI_TYPE` |

### .env File Format

Create a `.env` file in your project root:

```bash
# Service Configuration
AIPERF_LOG_LEVEL=DEBUG
AIPERF_VERBOSE=true
AIPERF_RECORD_PROCESSOR_SERVICE_COUNT=4
AIPERF_UI_TYPE=dashboard

# Developer Configuration
AIPERF_DEVELOPER__TRACE_SERVICES=worker,loadgen
```

**Nested Configuration**: Use double underscores (`__`) to access nested configuration fields.

### Environment Variable Examples

#### Setting Log Level

```bash
# Set log level to DEBUG
export AIPERF_LOG_LEVEL=DEBUG

# Or in .env file
AIPERF_LOG_LEVEL=DEBUG
```

#### Configuring Workers

```bash
# Set the number of record processor services
export AIPERF_RECORD_PROCESSOR_SERVICE_COUNT=8

# Set worker count
export AIPERF_WORKERS__COUNT=16
```

#### Enabling Verbose Logging

```bash
# Enable verbose logging
export AIPERF_VERBOSE=true

# Or extra verbose (TRACE level)
export AIPERF_EXTRA_VERBOSE=true
```

## Communication Configuration

### Communication Config Property

The `comm_config` property provides access to the active communication configuration:

```python
@property
def comm_config(self) -> BaseZMQCommunicationConfig:
    """Get the communication configuration."""
    if not self._comm_config:
        raise ValueError(
            "Communication configuration is not set. Please provide a valid configuration."
        )
    return self._comm_config
```

This property is populated by the `validate_comm_config` validator during model initialization.

### Communication Config Validation

The validator ensures only one communication mode is active:

```python
@model_validator(mode="after")
def validate_comm_config(self) -> Self:
    """Initialize the comm_config based on the zmq_tcp or zmq_ipc config."""
    _logger.debug(
        f"Validating comm_config: tcp: {self.zmq_tcp}, ipc: {self.zmq_ipc}"
    )
    if self.zmq_tcp is not None and self.zmq_ipc is not None:
        raise ValueError(
            "Cannot use both ZMQ TCP and ZMQ IPC configuration at the same time"
        )
    elif self.zmq_tcp is not None:
        _logger.info("Using ZMQ TCP configuration")
        self._comm_config = self.zmq_tcp
    elif self.zmq_ipc is not None:
        _logger.info("Using ZMQ IPC configuration")
        self._comm_config = self.zmq_ipc
    else:
        _logger.info("Using default ZMQ IPC configuration")
        self._comm_config = ZMQIPCConfig()
    return self
```

### ZMQ IPC Configuration Details

IPC (Inter-Process Communication) is the default and recommended communication mode for single-machine deployments:

```python
from aiperf.common.config.zmq_config import ZMQIPCConfig

config = ZMQIPCConfig(
    socket_dir="/tmp/aiperf/sockets",  # Directory for Unix domain sockets
)
```

**Advantages**:
- Lowest latency (no network stack overhead)
- Highest throughput
- No port conflicts
- Automatic cleanup of socket files

**Use Cases**:
- Local development
- Single-machine benchmarking
- Services on the same host

### ZMQ TCP Configuration Details

TCP configuration enables distributed service deployment:

```python
from aiperf.common.config.zmq_config import ZMQTCPConfig

config = ZMQTCPConfig(
    host="127.0.0.1",
    port=5555,
    bind_to_random_port=False,
)
```

**Advantages**:
- Network-based communication
- Multi-machine deployments
- Container orchestration compatibility

**Use Cases**:
- Distributed benchmarking
- Kubernetes deployments
- Multi-host testing

## Service Orchestration

### Record Processor Service Count

Controls the number of parallel record processing services:

```python
record_processor_service_count: Annotated[
    int | None,
    Field(
        ge=1,
        description="Number of services to spawn for processing records. "
        "The higher the request rate, the more services should be spawned "
        "in order to keep up with the incoming records. If not specified, "
        "the number of services will be automatically determined based on "
        "the worker count.",
    ),
    CLIParameter(
        name=("--record-processor-service-count", "--record-processors"),
        group=_CLI_GROUP,
    ),
] = ServiceDefaults.RECORD_PROCESSOR_SERVICE_COUNT
```

**Default**: `None` (auto-determined)

**CLI Flags**: `--record-processor-service-count`, `--record-processors`

**Auto-Determination Logic**: When not specified, AIPerf calculates an optimal count based on:
- Worker count
- Expected request rate
- System resources

**Manual Configuration**:

```python
# For high request rates, increase the count
config = ServiceConfig(
    record_processor_service_count=8
)
```

```bash
# Via CLI
aiperf profile --record-processor-service-count 8 config.yaml

# Via environment variable
export AIPERF_RECORD_PROCESSOR_SERVICE_COUNT=8
```

### Service Orchestration Patterns

#### Single Controller Pattern

The SystemController manages all services:

```python
from aiperf.controller.system_controller import SystemController

async def main():
    controller = SystemController(
        user_config=user_config,
        service_config=service_config,
    )

    await controller.start()
    await controller.wait_for_completion()
    await controller.stop()
```

#### Multi-Service Coordination

Services communicate through ZMQ patterns:

1. **Pub/Sub**: Broadcast messages to multiple subscribers
2. **Push/Pull**: Load-balanced task distribution
3. **Request/Reply**: Synchronous request-response
4. **Router/Dealer**: Advanced routing patterns

## Logging Configuration

### Log Level

Controls the verbosity of logging output:

```python
log_level: Annotated[
    AIPerfLogLevel,
    Field(
        description="Logging level",
    ),
    CLIParameter(
        name=("--log-level"),
        group=_CLI_GROUP,
    ),
] = ServiceDefaults.LOG_LEVEL
```

**Default**: `AIPerfLogLevel.INFO`

**Available Levels**:
- `TRACE`: Most verbose, includes all debugging details
- `DEBUG`: Detailed debugging information
- `INFO`: General informational messages
- `NOTICE`: Notable events (between INFO and WARNING)
- `WARNING`: Warning messages
- `SUCCESS`: Success notifications (between WARNING and ERROR)
- `ERROR`: Error messages
- `CRITICAL`: Critical failures

**Usage**:

```python
# Programmatic
config = ServiceConfig(log_level=AIPerfLogLevel.DEBUG)

# CLI
aiperf profile --log-level DEBUG config.yaml

# Environment variable
export AIPERF_LOG_LEVEL=DEBUG
```

### Verbose Flag

Shortcut for DEBUG level logging:

```python
verbose: Annotated[
    bool,
    Field(
        description="Equivalent to --log-level DEBUG. Enables more verbose "
        "logging output, but lacks some raw message logging.",
        json_schema_extra={ADD_TO_TEMPLATE: False},
    ),
    CLIParameter(
        name=("--verbose", "-v"),
        group=_CLI_GROUP,
    ),
] = ServiceDefaults.VERBOSE
```

**Default**: `False`

**CLI Flags**: `--verbose`, `-v`

**Note**: The `verbose` flag is converted to `log_level=DEBUG` during validation.

### Extra Verbose Flag

Shortcut for TRACE level logging:

```python
extra_verbose: Annotated[
    bool,
    Field(
        description="Equivalent to --log-level TRACE. Enables the most "
        "verbose logging output possible.",
        json_schema_extra={ADD_TO_TEMPLATE: False},
    ),
    CLIParameter(
        name=("--extra-verbose", "-vv"),
        group=_CLI_GROUP,
    ),
] = ServiceDefaults.EXTRA_VERBOSE
```

**Default**: `False`

**CLI Flags**: `--extra-verbose`, `-vv`

**Usage**:

```bash
# Debug level
aiperf profile -v config.yaml

# Trace level
aiperf profile -vv config.yaml
```

### Log Level Validation

The validator automatically sets log_level based on verbose flags:

```python
@model_validator(mode="after")
def validate_log_level_from_verbose_flags(self) -> Self:
    """Set log level based on verbose flags."""
    if self.extra_verbose:
        self.log_level = AIPerfLogLevel.TRACE
    elif self.verbose:
        self.log_level = AIPerfLogLevel.DEBUG
    return self
```

**Priority Order**:
1. `extra_verbose` flag (sets TRACE)
2. `verbose` flag (sets DEBUG)
3. `log_level` parameter
4. Default value (INFO)

## Worker Configuration

### Workers Config

The `workers` field configures worker behavior:

```python
workers: Annotated[
    WorkersConfig,
    Field(
        description="Worker configuration",
    ),
] = WorkersConfig()
```

**WorkersConfig Structure**:

```python
from aiperf.common.config.worker_config import WorkersConfig

config = ServiceConfig(
    workers=WorkersConfig(
        count=16,                # Number of workers
        max_queue_size=1000,     # Maximum queue size per worker
    )
)
```

### Worker Count Optimization

Choose worker count based on your workload:

**CPU-Bound Workloads**:
```python
import multiprocessing

workers = WorkersConfig(
    count=multiprocessing.cpu_count()
)
```

**I/O-Bound Workloads**:
```python
workers = WorkersConfig(
    count=multiprocessing.cpu_count() * 2
)
```

**High Throughput Requirements**:
```python
workers = WorkersConfig(
    count=32,  # Higher count for maximum throughput
    max_queue_size=2000,
)
```

## UI Type Selection

### UI Type Configuration

Controls the user interface mode:

```python
ui_type: Annotated[
    AIPerfUIType,
    Field(
        description="Type of UI to use",
    ),
    CLIParameter(
        name=("--ui-type", "--ui"),
        group=_CLI_GROUP,
    ),
] = ServiceDefaults.UI_TYPE
```

**Default**: `AIPerfUIType.TQDM`

**Available Types**:
- `DASHBOARD`: Rich terminal dashboard with real-time metrics
- `TQDM`: Progress bar interface (default)
- `NO_UI`: No UI output (headless mode)

### UI Type Usage

```python
# Dashboard UI (recommended for development)
config = ServiceConfig(ui_type=AIPerfUIType.DASHBOARD)

# TQDM UI (default)
config = ServiceConfig(ui_type=AIPerfUIType.TQDM)

# No UI (for CI/CD)
config = ServiceConfig(ui_type=AIPerfUIType.NO_UI)
```

```bash
# CLI usage
aiperf profile --ui-type dashboard config.yaml
aiperf profile --ui tqdm config.yaml
aiperf profile --ui no-ui config.yaml
```

### UI Type Selection Guidelines

**Use DASHBOARD when**:
- Interactive development
- Real-time monitoring required
- Multiple metrics need simultaneous viewing
- Log inspection is important

**Use TQDM when**:
- Simple progress indication is sufficient
- Running in standard terminals
- Minimal UI overhead desired

**Use NO_UI when**:
- Running in CI/CD pipelines
- Headless environments
- Output will be parsed programmatically
- Minimal resource usage required

## Developer Configuration

### Developer Config

Advanced configuration for developers:

```python
developer: DeveloperConfig = DeveloperConfig()
```

**DeveloperConfig Structure**:

```python
from aiperf.common.config.dev_config import DeveloperConfig

config = ServiceConfig(
    developer=DeveloperConfig(
        trace_services={"worker", "loadgen"},
        debug_services={"controller"},
        profiling_enabled=True,
    )
)
```

### Trace Services

Enable TRACE logging for specific services:

```python
config = ServiceConfig(
    developer=DeveloperConfig(
        trace_services={"worker", "loadgen", "record_processor"}
    )
)
```

```bash
# Via environment variable
export AIPERF_DEVELOPER__TRACE_SERVICES="worker,loadgen"
```

### Debug Services

Enable DEBUG logging for specific services:

```python
config = ServiceConfig(
    developer=DeveloperConfig(
        debug_services={"controller", "dataset_manager"}
    )
)
```

### Service-Specific Logging

The logging system checks service IDs against configured trace/debug services:

```python
def _is_service_in_types(service_id: str, service_types: set[ServiceType]) -> bool:
    """Check if a service is in a set of services."""
    for service_type in service_types:
        if (
            service_id == service_type
            or service_id.startswith(f"{service_type}_")
        ):
            return True
    return False
```

This enables fine-grained control over logging verbosity per service.

## Validation and Lifecycle

### Model Validators

ServiceConfig uses Pydantic validators for initialization logic:

#### Log Level Validator

```python
@model_validator(mode="after")
def validate_log_level_from_verbose_flags(self) -> Self:
    """Set log level based on verbose flags."""
    if self.extra_verbose:
        self.log_level = AIPerfLogLevel.TRACE
    elif self.verbose:
        self.log_level = AIPerfLogLevel.DEBUG
    return self
```

**Execution**: After all fields are set
**Purpose**: Converts verbose flags to log_level

#### Communication Config Validator

```python
@model_validator(mode="after")
def validate_comm_config(self) -> Self:
    """Initialize the comm_config based on the zmq_tcp or zmq_ipc config."""
    if self.zmq_tcp is not None and self.zmq_ipc is not None:
        raise ValueError(
            "Cannot use both ZMQ TCP and ZMQ IPC configuration at the same time"
        )
    elif self.zmq_tcp is not None:
        self._comm_config = self.zmq_tcp
    elif self.zmq_ipc is not None:
        self._comm_config = self.zmq_ipc
    else:
        self._comm_config = ZMQIPCConfig()
    return self
```

**Execution**: After all fields are set
**Purpose**: Initializes communication configuration with defaults

### Validation Order

Pydantic executes validators in this order:

1. Field-level validators
2. `mode="before"` model validators
3. Field assignment and type coercion
4. `mode="after"` model validators (ServiceConfig validators)
5. Final validation

### Configuration Loading

```python
def load_service_config() -> ServiceConfig:
    """Load service configuration from environment and defaults."""
    return ServiceConfig()
```

This function creates a ServiceConfig instance, loading from:
1. Environment variables (AIPERF_* prefix)
2. .env file (if present)
3. Defaults from ServiceDefaults

## Integration Patterns

### Service Initialization

All services receive ServiceConfig during initialization:

```python
class MyService(BaseService):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.service_config = service_config
        self.user_config = user_config

        # Access configuration
        self.log_level = service_config.log_level
        self.comm = service_config.comm_config
```

### Factory Pattern Integration

ServiceConfig works with the ServiceFactory:

```python
from aiperf.common.factories import ServiceFactory
from aiperf.common.enums import ServiceType

# Create a service instance with configuration
service = ServiceFactory.create_instance(
    service_type=ServiceType.WORKER,
    service_config=service_config,
    user_config=user_config,
)
```

### Multi-Process Service Management

ServiceConfig is serialized and passed to child processes:

```python
from multiprocessing import Process

def service_process(service_config: ServiceConfig):
    # Child process receives configuration
    setup_child_process_logging(service_config=service_config)

    # Initialize service with configuration
    service = MyService(service_config=service_config)
    asyncio.run(service.run())

# Start service in separate process
process = Process(
    target=service_process,
    args=(service_config,)
)
process.start()
```

### Configuration Inheritance

Create specialized configurations by subclassing:

```python
class CustomServiceConfig(ServiceConfig):
    """Custom service configuration with additional fields."""

    custom_field: str = "default_value"
    custom_timeout: int = 30

    @model_validator(mode="after")
    def validate_custom_config(self) -> Self:
        """Custom validation logic."""
        if self.custom_timeout < 0:
            raise ValueError("Timeout must be positive")
        return self
```

### Configuration Composition

Combine ServiceConfig with UserConfig:

```python
class BenchmarkRunner:
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
    ):
        self.service_config = service_config
        self.user_config = user_config

    def configure_services(self):
        """Configure services using both configs."""
        log_level = self.service_config.log_level
        output_dir = self.user_config.output.artifact_directory
        model = self.user_config.endpoint.model_names[0]

        return {
            "log_level": log_level,
            "output_dir": output_dir,
            "model": model,
        }
```

### Testing Configuration

Create test configurations easily:

```python
import pytest
from aiperf.common.config import ServiceConfig
from aiperf.common.enums import AIPerfLogLevel, AIPerfUIType

@pytest.fixture
def test_service_config():
    """Create a test service configuration."""
    return ServiceConfig(
        log_level=AIPerfLogLevel.DEBUG,
        ui_type=AIPerfUIType.NO_UI,
        record_processor_service_count=2,
    )

def test_my_feature(test_service_config):
    """Test using the service configuration."""
    assert test_service_config.log_level == AIPerfLogLevel.DEBUG
```

### Configuration Serialization

ServiceConfig can be serialized to various formats:

```python
# To dictionary
config_dict = service_config.model_dump()

# To JSON
config_json = service_config.model_dump_json(indent=2)

# To YAML (using BaseConfig method)
config_yaml = service_config.serialize_to_yaml(verbose=True)
```

### Configuration from Files

Load configuration from files:

```python
import json
from pathlib import Path

# From JSON
with open("service_config.json") as f:
    config = ServiceConfig(**json.load(f))

# From environment file
# (automatically loaded if .env exists)
config = ServiceConfig()
```

## Advanced Configuration Patterns

### Dynamic Configuration

Adjust configuration based on runtime conditions:

```python
def create_service_config(
    environment: str,
    high_throughput: bool = False,
) -> ServiceConfig:
    """Create service configuration based on environment."""

    if environment == "production":
        log_level = AIPerfLogLevel.WARNING
        ui_type = AIPerfUIType.NO_UI
    elif environment == "development":
        log_level = AIPerfLogLevel.DEBUG
        ui_type = AIPerfUIType.DASHBOARD
    else:
        log_level = AIPerfLogLevel.INFO
        ui_type = AIPerfUIType.TQDM

    if high_throughput:
        record_processor_count = 16
    else:
        record_processor_count = 4

    return ServiceConfig(
        log_level=log_level,
        ui_type=ui_type,
        record_processor_service_count=record_processor_count,
    )
```

### Configuration Profiles

Define configuration profiles for common scenarios:

```python
class ServiceConfigProfiles:
    """Predefined service configuration profiles."""

    @staticmethod
    def development() -> ServiceConfig:
        """Development profile with verbose logging."""
        return ServiceConfig(
            log_level=AIPerfLogLevel.DEBUG,
            ui_type=AIPerfUIType.DASHBOARD,
            record_processor_service_count=2,
        )

    @staticmethod
    def production() -> ServiceConfig:
        """Production profile optimized for performance."""
        return ServiceConfig(
            log_level=AIPerfLogLevel.WARNING,
            ui_type=AIPerfUIType.NO_UI,
            record_processor_service_count=8,
        )

    @staticmethod
    def testing() -> ServiceConfig:
        """Testing profile for CI/CD."""
        return ServiceConfig(
            log_level=AIPerfLogLevel.INFO,
            ui_type=AIPerfUIType.NO_UI,
            record_processor_service_count=1,
        )

# Usage
config = ServiceConfigProfiles.development()
```

### Configuration Validation

Implement custom validation for complex requirements:

```python
def validate_service_config(config: ServiceConfig) -> list[str]:
    """Validate service configuration and return any errors."""
    errors = []

    if config.record_processor_service_count:
        if config.record_processor_service_count > 32:
            errors.append(
                "Record processor count should not exceed 32 for optimal performance"
            )

    if config.zmq_tcp and config.zmq_ipc:
        errors.append("Cannot use both TCP and IPC communication")

    return errors

# Usage
errors = validate_service_config(service_config)
if errors:
    for error in errors:
        print(f"Configuration error: {error}")
```

## Key Takeaways

1. **ServiceConfig is the Central Configuration**: All AIPerf services receive and use ServiceConfig for runtime behavior.

2. **Environment-Aware**: Automatically loads from environment variables with the AIPERF_ prefix and .env files.

3. **Type-Safe with Pydantic**: Full type safety and validation through Pydantic Settings.

4. **CLI Integration**: Seamless integration with Cyclopts for command-line configuration.

5. **Communication Flexibility**: Supports both TCP and IPC communication modes, with IPC as the default.

6. **Automatic Validation**: Model validators ensure configuration consistency and set intelligent defaults.

7. **Service Orchestration**: Controls service count, worker configuration, and coordination.

8. **Logging Control**: Fine-grained logging configuration with service-specific log levels.

9. **Developer Features**: Advanced debugging capabilities through DeveloperConfig.

10. **Extensible Design**: The `extra="allow"` setting permits custom fields for specialized services.

11. **Serialization Support**: Can be serialized to JSON, YAML, and other formats for persistence and debugging.

12. **Testing-Friendly**: Easy to create test configurations with custom values.

## Navigation

- Previous: [Chapter 30: User Configuration System](chapter-30-userconfig-deep-dive.md)
- Next: [Chapter 32: CLI Integration](chapter-32-cli-integration.md)
- [Back to Index](INDEX.md)
