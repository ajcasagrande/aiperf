<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Developers Guide

**Version:** 0.1.1
**Last Updated:** 2025-10-02

This guide provides comprehensive documentation for developers looking to extend or contribute to AIPerf. It covers architecture, design patterns, extensibility points, and best practices with complete working examples.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Design Patterns](#core-design-patterns)
3. [Factory System](#factory-system)
4. [Extending AIPerf](#extending-aiperf)
5. [Service Architecture](#service-architecture)
6. [Metrics System](#metrics-system)
7. [Dataset System](#dataset-system)
8. [Client System](#client-system)
9. [Communication System](#communication-system)
10. [Configuration System](#configuration-system)
11. [Best Practices](#best-practices)
12. [Development Workflow](#development-workflow)

---

## Architecture Overview

AIPerf is a distributed, multiprocess benchmarking framework designed for performance testing of AI inference services. The architecture follows a service-oriented design with message-passing for inter-process communication.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SystemController                            │
│  (Orchestrates lifecycle and manages all services)              │
└───────────────┬─────────────────────────────────────────────────┘
                │
    ┌───────────┴──────────────┐
    │   Message Bus (ZMQ)       │
    │   PUB/SUB, PUSH/PULL      │
    └───────┬──────────────┬────┘
            │              │
    ┌───────▼────┐    ┌────▼──────────┐
    │  Dataset   │    │    Timing     │
    │  Manager   │    │    Manager    │
    └────────────┘    └───────┬───────┘
                              │
                    ┌─────────▼─────────┐
                    │   Worker Manager  │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼────────────────────┐
        │                     │                    │
    ┌───▼────┐          ┌────▼────┐         ┌─────▼────┐
    │ Worker │          │ Worker  │   ...   │  Worker  │
    │   1    │          │    2    │         │    N     │
    └───┬────┘          └────┬────┘         └─────┬────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  Records Manager │
                    └────────┬─────────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
        ┌──────▼──────────┐       ┌───────▼──────────┐
        │ Record Processor│       │ Results Processor│
        │   (Distributed) │       │   (Aggregation)  │
        └─────────────────┘       └──────────────────┘
```

### Key Components

- **SystemController**: Central orchestrator managing service lifecycle
- **ServiceManager**: Manages service deployment (multiprocess or Kubernetes)
- **Workers**: Execute inference requests against target services
- **DatasetManager**: Provides conversation data to workers
- **TimingManager**: Controls request scheduling and rate limiting
- **RecordsManager**: Collects and aggregates performance data
- **RecordProcessor**: Computes per-request metrics
- **ResultsProcessor**: Aggregates metrics across all requests

### Core Principles

1. **Service-Oriented**: Each component is an independent service
2. **Message-Driven**: Services communicate via ZeroMQ message bus
3. **Factory-Based**: Extensibility through factory pattern
4. **Protocol-Driven**: Implementations defined by protocol interfaces
5. **Lifecycle-Managed**: All services follow init → start → stop lifecycle
6. **Type-Safe**: Extensive use of Pydantic for configuration validation

---

## Core Design Patterns

### 1. Factory Pattern

AIPerf extensively uses the Factory pattern for extensibility. All major subsystems are factory-driven:

```python
# Base factory pattern
class AIPerfFactory(Generic[ClassEnumT, ClassProtocolT]):
    """Generic factory for creating instances based on enum types"""

    @classmethod
    def register(cls, class_type: ClassEnumT, override_priority: int = 0):
        """Decorator for registering implementations"""
        ...

    @classmethod
    def create_instance(cls, class_type: ClassEnumT, **kwargs) -> ClassProtocolT:
        """Create instance of registered implementation"""
        ...
```

**Key Features:**
- Type-safe with generics
- Override priority for custom implementations
- Automatic registration via decorators
- Singleton variants for shared resources

### 2. Protocol-Based Design

AIPerf defines behavior through Protocol classes (structural typing):

```python
from typing import Protocol

class InferenceClientProtocol(Protocol):
    """Protocol defining inference client interface"""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None: ...

    async def send_request(
        self, model_endpoint: ModelEndpointInfo, payload: dict
    ) -> RequestRecord: ...

    async def close(self) -> None: ...
```

**Benefits:**
- Duck typing with type safety
- Clear contracts for implementations
- Easy to test with mocks
- Flexible implementation requirements

### 3. Hook-Based Lifecycle

Services use decorators to hook into lifecycle events:

```python
from aiperf.common.hooks import on_init, on_start, on_stop, on_command

class MyService(BaseService):
    @on_init
    async def _initialize_resources(self) -> None:
        """Called during service initialization"""
        self.resource = await create_resource()

    @on_start
    async def _start_processing(self) -> None:
        """Called when service starts"""
        await self.resource.start()

    @on_command(CommandType.PROFILE_START)
    async def _handle_profile_start(self, message: ProfileStartCommand) -> None:
        """Called when receiving PROFILE_START command"""
        await self.begin_profiling()

    @on_stop
    async def _cleanup(self) -> None:
        """Called during shutdown"""
        await self.resource.close()
```

### 4. Message-Passing Architecture

Services communicate through typed messages:

```python
# Publishing a message
await self.publish(
    StatusMessage(
        service_id=self.service_id,
        service_type=self.service_type,
        state=LifecycleState.RUNNING,
    )
)

# Subscribing to messages
@on_message(MessageType.STATUS)
async def _handle_status(self, message: StatusMessage) -> None:
    self.info(f"Service {message.service_id} is {message.state}")
```

**Message Types:**
- **Commands**: Request-response with acknowledgment
- **Messages**: Broadcast notifications
- **Push/Pull**: Work distribution patterns
- **Request/Reply**: RPC-style communication

### 5. Metrics System

Metrics use a declarative, dependency-aware system:

```python
class MyMetric(BaseRecordMetric[int]):
    """Metric computed from individual records"""

    tag = "my_metric"
    header = "My Custom Metric"
    unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.NONE
    required_metrics = {"request_latency"}  # Dependencies

    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> int:
        """Compute metric value from record"""
        latency = record_metrics["request_latency"]
        return latency * 2  # Example computation
```

---

## Factory System

AIPerf provides 15+ factory types for extending different subsystems. Each factory follows the same pattern but has type-specific requirements.

### Factory Types

| Factory | Enum Type | Protocol | Purpose |
|---------|-----------|----------|---------|
| `InferenceClientFactory` | `EndpointType` | `InferenceClientProtocol` | HTTP clients for inference endpoints |
| `RequestConverterFactory` | `EndpointType` | `RequestConverterProtocol` | Request payload formatting |
| `ResponseExtractorFactory` | `EndpointType` | `ResponseExtractorProtocol` | Response parsing |
| `ComposerFactory` | `ComposerType` | `BaseDatasetComposer` | Dataset generation strategies |
| `CustomDatasetFactory` | `CustomDatasetType` | `CustomDatasetLoaderProtocol` | Custom dataset loaders |
| `ServiceFactory` | `ServiceType` | `ServiceProtocol` | System services |
| `ServiceManagerFactory` | `ServiceRunType` | `ServiceManagerProtocol` | Service deployment managers |
| `DataExporterFactory` | `DataExporterType` | `DataExporterProtocol` | Results export formats |
| `ConsoleExporterFactory` | `ConsoleExporterType` | `ConsoleExporterProtocol` | Console output formats |
| `RequestRateGeneratorFactory` | `RequestRateMode` | `RequestRateGeneratorProtocol` | Request scheduling strategies |
| `RecordProcessorFactory` | `RecordProcessorType` | `RecordProcessorProtocol` | Per-record metric processors |
| `ResultsProcessorFactory` | `ResultsProcessorType` | `ResultsProcessorProtocol` | Aggregate metric processors |
| `CommunicationFactory` | `CommunicationBackend` | `CommunicationProtocol` | Message bus implementations |
| `CommunicationClientFactory` | `CommClientType` | `CommunicationClientProtocol` | Messaging clients |
| `ZMQProxyFactory` | `ZMQProxyType` | `BaseZMQProxy` | ZMQ proxy configurations |

### Using Factories

```python
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.enums import EndpointType

# Create an instance
client = InferenceClientFactory.create_instance(
    EndpointType.CHAT,
    model_endpoint=my_endpoint_info,
)

# Get registered class without instantiating
client_class = InferenceClientFactory.get_class_from_type(EndpointType.CHAT)

# List all registered types
all_types = InferenceClientFactory.get_all_class_types()
```

### Singleton Factories

Some factories create singleton instances (one per process):

```python
from aiperf.common.factories import CommunicationFactory

# First call creates instance
comms = CommunicationFactory.create_instance(
    CommunicationBackend.ZMQ,
    config=zmq_config,
)

# Subsequent calls return same instance
same_comms = CommunicationFactory.get_instance(CommunicationBackend.ZMQ)
```

---

## Extending AIPerf

This section provides complete, working examples for extending each factory type.

### 1. Custom Inference Client

**Use Case:** Add support for a custom inference API.

```python
# File: aiperf/clients/custom/my_api_client.py

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.models import RequestRecord, InferenceServerResponse, TextResponse
import aiohttp
import time

@InferenceClientFactory.register(EndpointType.CUSTOM_API)
class MyAPIClient:
    """Custom inference client for MyAPI service."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        self.model_endpoint = model_endpoint
        self.session: aiohttp.ClientSession | None = None

    async def initialize(self) -> None:
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession()

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: dict,
    ) -> RequestRecord:
        """Send request to MyAPI endpoint."""
        record = RequestRecord(start_perf_ns=time.perf_counter_ns())

        try:
            async with self.session.post(
                model_endpoint.endpoint.url,
                json=payload,
                headers={"Authorization": f"Bearer {model_endpoint.endpoint.api_key}"},
            ) as response:
                response.raise_for_status()
                text = await response.text()

                record.responses.append(
                    TextResponse(
                        text=text,
                        perf_ns=time.perf_counter_ns(),
                    )
                )
        except Exception as e:
            record.error = str(e)

        return record

    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
```

**Usage:**

```python
# Add custom endpoint type to enum (in aiperf/common/enums/endpoints_enums.py)
class EndpointType(CaseInsensitiveStrEnum):
    # ... existing types ...
    CUSTOM_API = "custom_api"

# Use in configuration
aiperf profile \
    --model my-model \
    --url https://api.example.com/v1/infer \
    --endpoint-type custom_api
```

### 2. Custom Request Converter

**Use Case:** Format requests for your custom API.

```python
# File: aiperf/clients/custom/my_api_converter.py

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.models import Turn

@RequestConverterFactory.register(EndpointType.CUSTOM_API)
class MyAPIRequestConverter:
    """Convert Turn objects to MyAPI request format."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict:
        """Format payload for MyAPI."""
        # Extract text content from turn
        prompt = ""
        for text in turn.texts:
            prompt += " ".join(text.contents)

        # Build MyAPI-specific payload
        payload = {
            "model_id": turn.model or model_endpoint.primary_model_name,
            "input_text": prompt,
            "parameters": {
                "max_tokens": turn.max_tokens,
                "temperature": 0.7,
            },
        }

        # Add endpoint-specific extras
        if model_endpoint.endpoint.extra:
            payload["parameters"].update(model_endpoint.endpoint.extra)

        return payload
```

### 3. Custom Response Extractor

**Use Case:** Parse responses from your custom API.

```python
# File: aiperf/parsers/my_api_parser.py

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.factories import ResponseExtractorFactory
from aiperf.common.models import (
    RequestRecord,
    ParsedResponse,
    TextResponseData,
    TextResponse,
)
from aiperf.common.utils import load_json_str

@ResponseExtractorFactory.register(EndpointType.CUSTOM_API)
class MyAPIResponseExtractor:
    """Extract response data from MyAPI responses."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        self.model_endpoint = model_endpoint

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Parse MyAPI responses into structured data."""
        results = []

        for response in record.responses:
            if not isinstance(response, TextResponse):
                continue

            try:
                # Parse JSON response
                data = load_json_str(response.text)

                # Extract generated text
                generated_text = data.get("output", {}).get("text", "")

                if generated_text:
                    results.append(
                        ParsedResponse(
                            perf_ns=response.perf_ns,
                            data=TextResponseData(text=generated_text),
                        )
                    )
            except Exception as e:
                # Log parsing errors but don't fail
                print(f"Failed to parse response: {e}")
                continue

        return results
```

### 4. Custom Dataset Composer

**Use Case:** Generate custom synthetic datasets.

```python
# File: aiperf/dataset/composer/custom_composer.py

from aiperf.common.config import UserConfig
from aiperf.common.enums import ComposerType
from aiperf.common.factories import ComposerFactory
from aiperf.common.models import Conversation, Turn, Text
from aiperf.common.tokenizer import Tokenizer
from aiperf.dataset.composer.base import BaseDatasetComposer
import uuid
import random

@ComposerFactory.register(ComposerType.CODE_GENERATION)
class CodeGenerationComposer(BaseDatasetComposer):
    """Generate code generation benchmark dataset."""

    def __init__(self, config: UserConfig, tokenizer: Tokenizer):
        super().__init__(config, tokenizer)

        self.programming_tasks = [
            "Write a function to reverse a string",
            "Implement binary search algorithm",
            "Create a class for a stack data structure",
            "Write a function to find prime numbers",
            # ... more tasks
        ]

    def create_dataset(self) -> list[Conversation]:
        """Generate code generation conversations."""
        conversations = []

        for _ in range(self.config.input.conversation.num):
            conversation = Conversation(session_id=str(uuid.uuid4()))

            # Create initial turn with programming task
            task = random.choice(self.programming_tasks)
            turn = Turn()
            turn.texts.append(
                Text(
                    name="user",
                    contents=[
                        f"You are a coding assistant. {task}. "
                        f"Provide clean, well-documented code."
                    ],
                )
            )

            self._finalize_turn(turn)
            conversation.turns.append(turn)
            conversations.append(conversation)

        return conversations
```

**Usage:**

```python
# Add enum value (in aiperf/common/enums/dataset_enums.py)
class ComposerType(CaseInsensitiveStrEnum):
    SYNTHETIC = "synthetic"
    CUSTOM = "custom"
    CODE_GENERATION = "code_generation"  # New type
```

### 5. Custom Dataset Loader

**Use Case:** Load datasets from custom file formats.

```python
# File: aiperf/dataset/loader/parquet_loader.py

from pathlib import Path
from aiperf.common.enums import CustomDatasetType
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.models import Conversation, Turn, Text
import pyarrow.parquet as pq
import uuid

@CustomDatasetFactory.register(CustomDatasetType.PARQUET)
class ParquetDatasetLoader:
    """Load datasets from Parquet files."""

    def __init__(self, file_path: Path, **kwargs):
        self.file_path = file_path

    def load(self) -> list[Conversation]:
        """Load conversations from Parquet file."""
        conversations = []

        # Read Parquet file
        table = pq.read_table(self.file_path)
        df = table.to_pandas()

        for _, row in df.iterrows():
            conversation = Conversation(
                session_id=row.get("session_id", str(uuid.uuid4()))
            )

            turn = Turn()
            turn.texts.append(
                Text(
                    name="user",
                    contents=[row["prompt"]],
                )
            )

            # Set max_tokens if available
            if "max_tokens" in row:
                turn.max_tokens = int(row["max_tokens"])

            conversation.turns.append(turn)
            conversations.append(conversation)

        return conversations
```

**Usage:**

```python
# Add enum value (in aiperf/common/enums/dataset_enums.py)
class CustomDatasetType(CaseInsensitiveStrEnum):
    SINGLE_TURN = "single_turn"
    MULTI_TURN = "multi_turn"
    MOONCAKE_TRACE = "mooncake_trace"
    PARQUET = "parquet"  # New type

# Use in CLI
aiperf profile \
    --input-file my_dataset.parquet \
    --custom-dataset-type parquet \
    --model my-model \
    --url http://localhost:8000
```

### 6. Custom Metric

**Use Case:** Add a custom performance metric.

```python
# File: aiperf/metrics/types/custom_metric.py

from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict

class ResponseQualityMetric(BaseRecordMetric[float]):
    """
    Custom metric measuring response quality score.

    This is a record-level metric computed for each request.
    """

    # Required metadata
    tag = "response_quality"
    header = "Response Quality Score"
    short_header = "Quality"
    unit = MetricTimeUnit.NONE  # Dimensionless score
    display_unit = None
    display_order = 500
    flags = MetricFlags.NONE

    # Dependencies (optional)
    required_metrics = {"output_token_count"}

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """Compute quality score from 0.0 to 1.0."""

        # Check dependencies
        self._check_metrics(record_metrics)

        if not record.responses:
            raise NoMetricValue("No responses to evaluate")

        output_tokens = record_metrics["output_token_count"]

        # Example: Score based on output length
        # In practice, use real quality metrics
        if output_tokens < 10:
            quality = 0.3
        elif output_tokens < 50:
            quality = 0.7
        else:
            quality = 1.0

        return quality


class AverageQualityMetric(BaseAggregateMetric[float]):
    """
    Aggregate metric computing average quality across all requests.

    This aggregates the record-level quality scores.
    """

    tag = "avg_quality"
    header = "Average Response Quality"
    unit = MetricTimeUnit.NONE
    display_order = 501
    flags = MetricFlags.NONE
    required_metrics = {"response_quality"}

    def _aggregate_init(self) -> None:
        """Initialize aggregation state."""
        self.total_quality = 0.0
        self.count = 0

    def _aggregate_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> None:
        """Accumulate quality scores."""
        quality = record_metrics["response_quality"]
        self.total_quality += quality
        self.count += 1

    def _aggregate_finalize(self) -> float:
        """Compute average quality."""
        if self.count == 0:
            raise NoMetricValue("No valid records to aggregate")
        return self.total_quality / self.count
```

**Metric Types:**

1. **BaseRecordMetric**: Computed per-request (TTFT, latency, etc.)
2. **BaseAggregateMetric**: Computed across requests (averages, totals)
3. **BaseDerivedMetric**: Computed from other metrics (throughput, rates)

**Metric Flags:**

```python
class MetricFlags(enum.IntFlag):
    NONE = 0
    STREAMING_TOKENS_ONLY = 1 << 0  # Only for streaming endpoints
    TOKENIZER_REQUIRED = 1 << 1     # Needs tokenizer
    ERROR_ONLY = 1 << 2             # Only for failed requests
    # ... more flags
```

### 7. Custom Service

**Use Case:** Add a new system service.

```python
# File: aiperf/services/custom_service.py

from aiperf.common.base_service import BaseService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType, CommandType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_init, on_start, on_stop, on_command, background_task

@ServiceFactory.register(ServiceType.CUSTOM_SERVICE)
class CustomService(BaseService):
    """Custom service for special processing."""

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
        )
        self.data_cache = {}

    @on_init
    async def _initialize_custom_service(self) -> None:
        """Called during initialization phase."""
        self.info("Initializing custom service")
        # Initialize resources
        self.data_cache = {}

    @on_start
    async def _start_custom_service(self) -> None:
        """Called when service starts."""
        self.info("Custom service started")

    @background_task(interval=5.0, immediate=True)
    async def _periodic_health_check(self) -> None:
        """Background task that runs every 5 seconds."""
        self.debug(f"Health check: cache size = {len(self.data_cache)}")

    @on_command(CommandType.PROFILE_START)
    async def _handle_profile_start(self, message) -> None:
        """Handle PROFILE_START command."""
        self.info("Starting profiling in custom service")
        # Begin custom processing

    @on_stop
    async def _cleanup_custom_service(self) -> None:
        """Called during shutdown."""
        self.info("Cleaning up custom service")
        self.data_cache.clear()
```

**Register in System:**

```python
# Add to ServiceType enum (in aiperf/common/enums/service_enums.py)
class ServiceType(CaseInsensitiveStrEnum):
    SYSTEM_CONTROLLER = "system_controller"
    DATASET_MANAGER = "dataset_manager"
    # ... existing types ...
    CUSTOM_SERVICE = "custom_service"  # New service

# Add to required_services in SystemController (if needed)
self.required_services: dict[ServiceTypeT, int] = {
    ServiceType.DATASET_MANAGER: 1,
    ServiceType.TIMING_MANAGER: 1,
    ServiceType.WORKER_MANAGER: 1,
    ServiceType.RECORDS_MANAGER: 1,
    ServiceType.CUSTOM_SERVICE: 1,  # Add custom service
}
```

### 8. Custom Data Exporter

**Use Case:** Export results in a custom format (e.g., database, cloud storage).

```python
# File: aiperf/exporters/database_exporter.py

from aiperf.common.enums import DataExporterType
from aiperf.common.factories import DataExporterFactory
from aiperf.exporters.exporter_config import ExporterConfig, FileExportInfo
import asyncpg

@DataExporterFactory.register(DataExporterType.DATABASE)
class DatabaseExporter:
    """Export results to PostgreSQL database."""

    def __init__(self, exporter_config: ExporterConfig) -> None:
        self.config = exporter_config
        self.conn = None

    def get_export_info(self) -> FileExportInfo:
        """Return export information."""
        return FileExportInfo(
            name="Database Export",
            description="Results exported to PostgreSQL",
            file_path=None,  # No file for database export
        )

    async def export(self) -> None:
        """Export results to database."""
        # Connect to database
        self.conn = await asyncpg.connect(
            host="localhost",
            database="aiperf_results",
            user="aiperf",
            password="password",
        )

        try:
            # Get results data
            results = self.config.results

            # Insert benchmark metadata
            run_id = await self.conn.fetchval(
                """
                INSERT INTO benchmark_runs (
                    timestamp, model_name, endpoint_url, request_count
                ) VALUES ($1, $2, $3, $4)
                RETURNING run_id
                """,
                results.timestamp,
                self.config.user_config.endpoint.model_names[0],
                self.config.user_config.endpoint.url,
                len(results.records),
            )

            # Insert individual metrics
            for metric in results.metrics:
                await self.conn.execute(
                    """
                    INSERT INTO metrics (
                        run_id, metric_name, value, unit
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    run_id,
                    metric.tag,
                    metric.value,
                    str(metric.unit),
                )

        finally:
            await self.conn.close()
```

**Usage:**

```python
# Add enum value
class DataExporterType(CaseInsensitiveStrEnum):
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    DATABASE = "database"  # New exporter

# Use in configuration
aiperf profile \
    --model my-model \
    --url http://localhost:8000 \
    --export-format database
```

### 9. Custom Request Rate Generator

**Use Case:** Implement custom request scheduling logic.

```python
# File: aiperf/timing/custom_rate_generator.py

from aiperf.common.enums import RequestRateMode
from aiperf.common.factories import RequestRateGeneratorFactory
from aiperf.timing.config import TimingManagerConfig
import math

@RequestRateGeneratorFactory.register(RequestRateMode.SINE_WAVE)
class SineWaveRateGenerator:
    """Generate request intervals following a sine wave pattern."""

    def __init__(self, config: TimingManagerConfig) -> None:
        self.config = config
        self.base_rate = config.request_rate or 10.0
        self.request_count = 0
        self.period = 100  # Complete cycle every 100 requests

    def next_interval(self) -> float:
        """Return time until next request."""
        # Generate sine wave between 0.5x and 1.5x base rate
        phase = (self.request_count % self.period) / self.period * 2 * math.pi
        rate_multiplier = 1.0 + 0.5 * math.sin(phase)
        current_rate = self.base_rate * rate_multiplier

        self.request_count += 1

        # Return interval in seconds
        return 1.0 / current_rate
```

**Usage:**

```python
# Add enum value
class RequestRateMode(CaseInsensitiveStrEnum):
    POISSON = "poisson"
    CONSTANT = "constant"
    CONCURRENCY_BURST = "concurrency_burst"
    SINE_WAVE = "sine_wave"  # New mode

# Use in configuration
aiperf profile \
    --model my-model \
    --url http://localhost:8000 \
    --request-rate 10 \
    --request-rate-mode sine_wave
```

### 10. Custom Console Exporter

**Use Case:** Customize terminal output format.

```python
# File: aiperf/exporters/custom_console_exporter.py

from aiperf.common.enums import ConsoleExporterType
from aiperf.common.factories import ConsoleExporterFactory
from aiperf.exporters.exporter_config import ExporterConfig
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

@ConsoleExporterFactory.register(ConsoleExporterType.DETAILED)
class DetailedConsoleExporter:
    """Custom detailed console output format."""

    def __init__(self, exporter_config: ExporterConfig) -> None:
        self.config = exporter_config

    async def export(self, console: Console) -> None:
        """Export results to console with detailed format."""
        results = self.config.results

        # Create summary table
        summary = Table(title="Benchmark Summary", show_header=True)
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="green")

        summary.add_row("Total Requests", str(len(results.records)))
        summary.add_row("Successful", str(results.success_count))
        summary.add_row("Failed", str(results.error_count))
        summary.add_row("Duration", f"{results.duration:.2f}s")

        console.print(summary)

        # Create metrics table with percentiles
        metrics_table = Table(title="Detailed Metrics", show_header=True)
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("P50", justify="right")
        metrics_table.add_column("P90", justify="right")
        metrics_table.add_column("P95", justify="right")
        metrics_table.add_column("P99", justify="right")
        metrics_table.add_column("Max", justify="right")

        for metric in results.metrics:
            if hasattr(metric, 'percentiles'):
                metrics_table.add_row(
                    metric.header,
                    f"{metric.percentiles.p50:.2f}",
                    f"{metric.percentiles.p90:.2f}",
                    f"{metric.percentiles.p95:.2f}",
                    f"{metric.percentiles.p99:.2f}",
                    f"{metric.max:.2f}",
                )

        console.print(metrics_table)

        # Add warnings panel if any
        if results.warnings:
            warnings_panel = Panel(
                "\n".join(results.warnings),
                title="⚠️  Warnings",
                border_style="yellow",
            )
            console.print(warnings_panel)
```

**Usage:**

```python
# Add enum value
class ConsoleExporterType(CaseInsensitiveStrEnum):
    STANDARD = "standard"
    DETAILED = "detailed"  # New format

# Use in configuration
aiperf profile \
    --model my-model \
    --url http://localhost:8000 \
    --console-format detailed
```

---

## Service Architecture

### Service Lifecycle

All services follow a consistent lifecycle:

```
┌──────────┐    initialize()    ┌─────────────┐    start()    ┌─────────┐
│  CREATED │ ──────────────────▶│ INITIALIZED │ ─────────────▶│ RUNNING │
└──────────┘                    └─────────────┘               └─────┬───┘
                                                                     │
                                                                  stop()
                                                                     │
                                                                     ▼
                                                               ┌─────────┐
                                                               │ STOPPED │
                                                               └─────────┘
```

### Service Base Classes

```python
# Hierarchy
BaseService
├── BaseComponentService (adds component-specific features)
│   ├── Worker
│   ├── DatasetManager
│   ├── TimingManager
│   └── RecordsManager
└── SystemController (orchestrator)
```

### Creating a Service

```python
from aiperf.common.base_service import BaseService
from aiperf.common.factories import ServiceFactory
from aiperf.common.enums import ServiceType

@ServiceFactory.register(ServiceType.MY_SERVICE)
class MyService(BaseService):
    def __init__(self, service_config, user_config, service_id=None):
        super().__init__(service_config, user_config, service_id)
        # Service-specific initialization
```

### Communication Patterns

**1. Publishing Messages (Broadcast)**

```python
from aiperf.common.messages import StatusMessage
from aiperf.common.enums import LifecycleState

await self.publish(
    StatusMessage(
        service_id=self.service_id,
        service_type=self.service_type,
        state=LifecycleState.RUNNING,
    )
)
```

**2. Subscribing to Messages**

```python
from aiperf.common.hooks import on_message
from aiperf.common.enums import MessageType

@on_message(MessageType.STATUS)
async def _handle_status(self, message: StatusMessage) -> None:
    self.info(f"Received status from {message.service_id}")
```

**3. Sending Commands**

```python
from aiperf.common.messages import ProfileStartCommand

response = await self.send_command_and_wait_for_response(
    ProfileStartCommand(service_id=self.service_id),
    target_service_id="timing_manager_abc123",
    timeout=30.0,
)
```

**4. Handling Commands**

```python
from aiperf.common.hooks import on_command
from aiperf.common.enums import CommandType
from aiperf.common.messages import CommandSuccessResponse

@on_command(CommandType.PROFILE_START)
async def _handle_profile_start(
    self, message: ProfileStartCommand
) -> CommandSuccessResponse:
    # Handle command
    return CommandSuccessResponse.from_command_message(
        message, self.service_id
    )
```

**5. Request/Reply Pattern**

```python
# Handling requests
from aiperf.common.hooks import on_request

@on_request(MessageType.CONVERSATION_REQUEST)
async def _handle_conversation_request(
    self, message: ConversationRequestMessage
) -> ConversationResponseMessage:
    conversation = self.get_next_conversation()
    return ConversationResponseMessage(
        service_id=self.service_id,
        conversation=conversation,
    )

# Making requests
response = await self.conversation_request_client.request(
    ConversationRequestMessage(service_id=self.service_id),
    timeout=10.0,
)
```

**6. Push/Pull Pattern (Work Distribution)**

```python
# Pushing work
await self.push_client.push(
    CreditDropMessage(
        service_id=self.service_id,
        phase=CreditPhase.PROFILING,
    )
)

# Pulling work
from aiperf.common.hooks import on_pull_message

@on_pull_message(MessageType.CREDIT_DROP)
async def _handle_credit(self, message: CreditDropMessage) -> None:
    await self.process_credit(message)
```

---

## Metrics System

### Metric Architecture

```
┌────────────────┐
│ BaseMetric     │  Abstract base with auto-registration
└────────┬───────┘
         │
    ┌────┴─────┬────────────────────┬──────────────────┐
    │          │                    │                  │
┌───▼────────┐ │              ┌─────▼────────┐  ┌─────▼────────┐
│ BaseRecord │ │              │ BaseAggregate│  │ BaseDerived  │
│ Metric     │ │              │ Metric       │  │ Metric       │
└────────────┘ │              └──────────────┘  └──────────────┘
               │
        Per-request          Across requests   From other metrics
        computation          aggregation       computation
```

### Metric Types

**1. Record Metrics** (per-request computation)

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import MetricTimeUnit, MetricFlags

class MyRecordMetric(BaseRecordMetric[int]):
    """Computed for each individual request."""

    tag = "my_record_metric"
    header = "My Record Metric"
    unit = MetricTimeUnit.MILLISECONDS
    display_order = 100
    flags = MetricFlags.NONE
    required_metrics = None  # Or {"dependency_metric"}

    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> int:
        """Compute metric from single record."""
        # Access record data
        start_ns = record.request.start_perf_ns
        end_ns = record.responses[-1].perf_ns

        # Access other metrics if needed
        if self.required_metrics:
            dependency = record_metrics["dependency_metric"]

        return end_ns - start_ns
```

**2. Aggregate Metrics** (accumulating across requests)

```python
from aiperf.metrics import BaseAggregateMetric

class MyAggregateMetric(BaseAggregateMetric[float]):
    """Accumulated across all requests."""

    tag = "my_aggregate_metric"
    header = "My Aggregate Metric"
    unit = MetricTimeUnit.MILLISECONDS
    display_order = 200
    flags = MetricFlags.NONE
    required_metrics = {"my_record_metric"}

    def _aggregate_init(self) -> None:
        """Initialize aggregation state."""
        self.total = 0.0
        self.count = 0

    def _aggregate_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> None:
        """Process each record."""
        value = record_metrics["my_record_metric"]
        self.total += value
        self.count += 1

    def _aggregate_finalize(self) -> float:
        """Compute final aggregated value."""
        return self.total / self.count if self.count > 0 else 0.0
```

**3. Derived Metrics** (computed from other metrics)

```python
from aiperf.metrics import BaseDerivedMetric

class MyDerivedMetric(BaseDerivedMetric[float]):
    """Computed from other aggregated metrics."""

    tag = "my_derived_metric"
    header = "My Derived Metric"
    unit = MetricTimeUnit.NONE
    display_order = 300
    flags = MetricFlags.NONE
    required_metrics = {"my_aggregate_metric", "total_requests"}

    def _derive(self, metrics: MetricResultsDict) -> float:
        """Compute from other metrics."""
        aggregate_value = metrics["my_aggregate_metric"]
        total_requests = metrics["total_requests"]

        return aggregate_value / total_requests
```

### Metric Flags

```python
from aiperf.common.enums import MetricFlags

# Available flags
MetricFlags.NONE                  # No special requirements
MetricFlags.STREAMING_TOKENS_ONLY  # Only for streaming endpoints
MetricFlags.TOKENIZER_REQUIRED     # Needs tokenizer to compute
MetricFlags.ERROR_ONLY             # Only for failed requests
MetricFlags.HIDDEN                 # Don't display in console
```

### Metric Units

```python
from aiperf.common.enums import (
    MetricTimeUnit,
    MetricSizeUnit,
    MetricOverTimeUnit,
    GenericMetricUnit,
)

# Time units
MetricTimeUnit.NANOSECONDS
MetricTimeUnit.MILLISECONDS
MetricTimeUnit.SECONDS

# Size units
MetricSizeUnit.TOKENS
MetricSizeUnit.BYTES

# Rate units
MetricOverTimeUnit.TOKENS_PER_SECOND
MetricOverTimeUnit.REQUESTS_PER_SECOND

# Generic units
GenericMetricUnit.COUNT
GenericMetricUnit.PERCENTAGE
```

### Metric Dependencies

Metrics can depend on other metrics. The system automatically resolves dependencies using topological sort:

```python
class DependentMetric(BaseRecordMetric[float]):
    tag = "dependent_metric"
    required_metrics = {"ttft", "request_latency"}  # Dependencies

    def _parse_record(self, record, record_metrics):
        ttft = record_metrics["ttft"]
        latency = record_metrics["request_latency"]
        return ttft / latency
```

**Dependency Rules:**
- Record metrics can depend on other record metrics
- Aggregate metrics can depend on record or aggregate metrics
- Derived metrics can depend on any metric type
- No circular dependencies allowed

### Using the Metric Registry

```python
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.common.enums import MetricFlags, MetricType

# Get all metric tags
all_tags = MetricRegistry.all_tags()

# Get metrics by criteria
streaming_tags = MetricRegistry.tags_applicable_to(
    required_flags=MetricFlags.STREAMING_TOKENS_ONLY,
    disallowed_flags=MetricFlags.ERROR_ONLY,
    MetricType.RECORD,
)

# Get metric class
metric_class = MetricRegistry.get_class("ttft")

# Get metric instance (singleton per process)
metric_instance = MetricRegistry.get_instance("ttft")

# Get dependency-ordered list
ordered_tags = MetricRegistry.create_dependency_order()
```

---

## Dataset System

### Dataset Architecture

```
                ┌──────────────────┐
                │ DatasetManager   │
                │   (Service)      │
                └────────┬─────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────▼───────┐                ┌───────▼────────┐
│   Composer    │                │     Loader     │
│  (Generate)   │                │  (Load File)   │
└───────┬───────┘                └───────┬────────┘
        │                                │
        └────────────┬───────────────────┘
                     │
              ┌──────▼───────┐
              │ Conversation │
              │  ┌──────┐    │
              │  │ Turn │    │
              │  └──┬───┘    │
              │     │        │
              │  ┌──▼────┐   │
              │  │ Text  │   │
              │  │ Image │   │
              │  │ Audio │   │
              │  └───────┘   │
              └──────────────┘
```

### Dataset Models

```python
from aiperf.common.models import Conversation, Turn, Text, Image, Audio

# Conversation: Collection of turns for a session
conversation = Conversation(session_id="unique-id")

# Turn: Single request in a conversation
turn = Turn(
    model="my-model",
    max_tokens=100,
    role="user",
    delay=1.0,  # Delay before this turn (seconds)
)

# Text content
turn.texts.append(
    Text(
        name="user",
        contents=["What is the meaning of life?"],
    )
)

# Image content (base64 data URL)
turn.images.append(
    Image(
        name="image_url",
        contents=["data:image/png;base64,iVBORw0KGgoAAAAN..."],
    )
)

# Audio content (format,base64)
turn.audios.append(
    Audio(
        name="input_audio",
        contents=["wav,UklGRiQAAABXQVZFZm10IBAAAA..."],
    )
)

conversation.turns.append(turn)
```

### Dataset Composer

Composers generate synthetic datasets:

```python
from aiperf.dataset.composer.base import BaseDatasetComposer
from aiperf.common.config import UserConfig
from aiperf.common.tokenizer import Tokenizer

class MyComposer(BaseDatasetComposer):
    def __init__(self, config: UserConfig, tokenizer: Tokenizer):
        super().__init__(config, tokenizer)
        # Composer-specific initialization

    def create_dataset(self) -> list[Conversation]:
        """Generate conversations based on config."""
        conversations = []

        for _ in range(self.config.input.conversation.num):
            conversation = self._create_conversation()
            conversations.append(conversation)

        return conversations

    def _create_conversation(self) -> Conversation:
        conversation = Conversation(session_id=str(uuid.uuid4()))

        # Use generators for synthetic content
        prompt = self.prompt_generator.generate(
            mean=self.config.input.prompt.input_tokens.mean,
            stddev=self.config.input.prompt.input_tokens.stddev,
        )

        turn = Turn()
        turn.texts.append(Text(name="user", contents=[prompt]))

        # Finalize turn (sets model name, max_tokens, etc.)
        self._finalize_turn(turn)

        conversation.turns.append(turn)
        return conversation
```

### Dataset Loader

Loaders read datasets from files:

```python
from typing import Protocol
from pathlib import Path
from aiperf.common.models import Conversation

class CustomDatasetLoaderProtocol(Protocol):
    """Protocol for custom dataset loaders."""

    def __init__(self, file_path: Path, **kwargs) -> None: ...

    def load(self) -> list[Conversation]: ...
```

**Example: JSON Lines Loader**

```python
# File format: one JSON object per line
# {"prompt": "Hello", "max_tokens": 50, "model": "my-model"}

from pathlib import Path
import json

class JSONLinesLoader:
    def __init__(self, file_path: Path, **kwargs):
        self.file_path = file_path

    def load(self) -> list[Conversation]:
        conversations = []

        with open(self.file_path) as f:
            for line in f:
                data = json.loads(line)

                conversation = Conversation(session_id=str(uuid.uuid4()))
                turn = Turn()
                turn.texts.append(
                    Text(name="user", contents=[data["prompt"]])
                )

                if "max_tokens" in data:
                    turn.max_tokens = data["max_tokens"]
                if "model" in data:
                    turn.model = data["model"]

                conversation.turns.append(turn)
                conversations.append(conversation)

        return conversations
```

### Generators

Built-in generators for synthetic content:

**Prompt Generator:**

```python
from aiperf.dataset.generator import PromptGenerator

prompt_generator = PromptGenerator(config.input.prompt, tokenizer)

# Generate synthetic prompt
prompt = prompt_generator.generate(mean=100, stddev=10)

# Get prefix prompt (system instructions)
prefix = prompt_generator.get_random_prefix_prompt()
```

**Image Generator:**

```python
from aiperf.dataset.generator import ImageGenerator

image_generator = ImageGenerator(config.input.image)

# Generate synthetic image (base64 data URL)
image_data = image_generator.generate()
```

**Audio Generator:**

```python
from aiperf.dataset.generator import AudioGenerator

audio_generator = AudioGenerator(config.input.audio)

# Generate synthetic audio (format,base64)
audio_data = audio_generator.generate()
```

---

## Client System

### Client Architecture

```
┌──────────────────────────────────────────────────┐
│ InferenceClient (HTTP Communication)             │
│                                                   │
│  ┌────────────────┐    ┌────────────────────┐   │
│  │ RequestConverter│───▶│ InferenceClient    │   │
│  │ (Format)        │    │ (HTTP)             │   │
│  └────────────────┘    └───────┬────────────┘   │
│                                 │                 │
│                          HTTP Request/Response   │
│                                 │                 │
│                        ┌────────▼────────┐        │
│                        │ ResponseExtractor│        │
│                        │ (Parse)          │        │
│                        └─────────────────┘        │
└──────────────────────────────────────────────────┘
```

### HTTP Client

The HTTP client handles communication with inference services:

```python
# File: aiperf/clients/http/aiohttp_client.py (simplified)

import aiohttp
import asyncio
from aiperf.common.models import RequestRecord, TextResponse, SSEMessage

class AIOHTTPClient:
    """Base HTTP client using aiohttp."""

    def __init__(self, model_endpoint):
        self.model_endpoint = model_endpoint
        self.session = None

    async def initialize(self):
        """Create HTTP session with connection pooling."""
        connector = aiohttp.TCPConnector(
            limit_per_host=AIPERF_HTTP_CONNECTION_LIMIT
        )
        self.session = aiohttp.ClientSession(connector=connector)

    async def send_request(self, model_endpoint, payload):
        """Send HTTP request to endpoint."""
        record = RequestRecord(start_perf_ns=time.perf_counter_ns())

        try:
            headers = {"Content-Type": "application/json"}
            if model_endpoint.endpoint.api_key:
                headers["Authorization"] = f"Bearer {model_endpoint.endpoint.api_key}"

            async with self.session.post(
                model_endpoint.endpoint.url,
                json=payload,
                headers=headers,
            ) as response:
                if model_endpoint.endpoint.streaming:
                    # Handle streaming response
                    async for line in response.content:
                        record.responses.append(
                            SSEMessage.from_bytes(line, time.perf_counter_ns())
                        )
                else:
                    # Handle non-streaming response
                    text = await response.text()
                    record.responses.append(
                        TextResponse(text=text, perf_ns=time.perf_counter_ns())
                    )
        except Exception as e:
            record.error = str(e)

        return record
```

### Request Converter

Converts Turn objects to API-specific payloads:

```python
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.enums import EndpointType

@RequestConverterFactory.register(EndpointType.CHAT)
class OpenAIChatCompletionRequestConverter:
    async def format_payload(self, model_endpoint, turn):
        """Format Turn to OpenAI chat completion format."""
        messages = []

        for text in turn.texts:
            messages.append({
                "role": turn.role or "user",
                "content": text.contents[0],
            })

        payload = {
            "model": turn.model or model_endpoint.primary_model_name,
            "messages": messages,
            "stream": model_endpoint.endpoint.streaming,
        }

        if turn.max_tokens:
            payload["max_completion_tokens"] = turn.max_tokens

        # Add extras from config
        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        return payload
```

### Response Extractor

Parses API responses into structured data:

```python
from aiperf.common.factories import ResponseExtractorFactory
from aiperf.common.enums import EndpointType, OpenAIObjectType
from aiperf.common.models import ParsedResponse, TextResponseData

@ResponseExtractorFactory.register(EndpointType.CHAT)
class OpenAIResponseExtractor:
    def __init__(self, model_endpoint):
        self.model_endpoint = model_endpoint

    async def extract_response_data(self, record):
        """Parse OpenAI response into ParsedResponse objects."""
        results = []

        for response in record.responses:
            # Parse JSON
            data = json.loads(response.text)

            # Handle different object types
            if data["object"] == "chat.completion":
                content = data["choices"][0]["message"]["content"]
            elif data["object"] == "chat.completion.chunk":
                content = data["choices"][0]["delta"].get("content", "")
            else:
                continue

            if content:
                results.append(
                    ParsedResponse(
                        perf_ns=response.perf_ns,
                        data=TextResponseData(text=content),
                    )
                )

        return results
```

### Model Endpoint Info

Configuration object for endpoints:

```python
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.config import UserConfig

# Create from user config
endpoint_info = ModelEndpointInfo.from_user_config(user_config)

# Access properties
endpoint_info.endpoint.url            # "http://localhost:8000/v1/chat/completions"
endpoint_info.endpoint.type           # EndpointType.CHAT
endpoint_info.endpoint.streaming      # True
endpoint_info.endpoint.api_key        # "sk-..."
endpoint_info.primary_model_name      # "gpt-4"
endpoint_info.endpoint.extra          # {"temperature": 0.7}
```

---

## Communication System

### ZeroMQ Architecture

AIPerf uses ZeroMQ for inter-process communication with multiple socket patterns:

```
┌───────────────────────────────────────────────────┐
│            ZMQ Proxy (Message Broker)             │
│                                                   │
│  ┌──────────────┐         ┌──────────────┐      │
│  │ PUB Frontend │◀───────▶│ SUB Backend  │      │
│  └──────────────┘  Proxy  └──────────────┘      │
│                                                   │
│  ┌──────────────┐         ┌──────────────┐      │
│  │PUSH Frontend │◀───────▶│ PULL Backend │      │
│  └──────────────┘         └──────────────┘      │
│                                                   │
│  ┌──────────────┐         ┌──────────────┐      │
│  │ REQ Frontend │◀───────▶│ REP Backend  │      │
│  └──────────────┘         └──────────────┘      │
└───────────────────────────────────────────────────┘
```

### Communication Patterns

**1. PUB/SUB (Broadcast)**
- Publisher broadcasts messages
- Multiple subscribers receive copies
- Used for: Status updates, commands, notifications

```python
# Publisher
await self.pub_client.publish(StatusMessage(...))

# Subscriber
@on_message(MessageType.STATUS)
async def _handle_status(self, message):
    pass
```

**2. PUSH/PULL (Load Balancing)**
- Pushers send work items
- Pullers receive round-robin
- Used for: Credit distribution, work queues

```python
# Pusher
await self.push_client.push(CreditDropMessage(...))

# Puller
@on_pull_message(MessageType.CREDIT_DROP)
async def _handle_credit(self, message):
    pass
```

**3. REQ/REP (Request-Reply)**
- Requester sends and waits
- Replier processes and responds
- Used for: Dataset requests, RPC calls

```python
# Requester
response = await self.req_client.request(
    ConversationRequestMessage(...), timeout=10.0
)

# Replier
@on_request(MessageType.CONVERSATION_REQUEST)
async def _handle_request(self, message):
    return ConversationResponseMessage(...)
```

### Creating Communication Clients

```python
from aiperf.common.enums import CommAddress, CommClientType

# In service __init__
self.pub_client = self.comms.create_pub_client(
    CommAddress.MESSAGE_BUS,
    bind=False,
)

self.push_client = self.comms.create_push_client(
    CommAddress.CREDIT_RETURN,
    bind=False,
)

self.req_client = self.comms.create_request_client(
    CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
    bind=False,
)
```

### Message Types

All messages inherit from BaseMessage:

```python
from aiperf.common.models import BaseMessage
from pydantic import Field

class MyCustomMessage(BaseMessage):
    """Custom message type."""

    message_type: MessageType = MessageType.CUSTOM
    service_id: str
    data: dict = Field(default_factory=dict)
```

### Communication Addresses

Addresses are defined in `CommAddress` enum:

```python
class CommAddress(CaseInsensitiveStrEnum):
    MESSAGE_BUS = "tcp://127.0.0.1:5555"
    CREDIT_DROP = "tcp://127.0.0.1:5556"
    CREDIT_RETURN = "tcp://127.0.0.1:5557"
    RAW_INFERENCE_PROXY_FRONTEND = "tcp://127.0.0.1:5558"
    DATASET_MANAGER_PROXY_FRONTEND = "tcp://127.0.0.1:5559"
    # ... more addresses
```

---

## Configuration System

### Configuration Hierarchy

```
UserConfig (Top-level CLI configuration)
├── EndpointConfig (Target service)
│   ├── type: EndpointType
│   ├── url: str
│   ├── model_names: list[str]
│   ├── streaming: bool
│   └── extra: dict
├── InputConfig (Dataset configuration)
│   ├── PromptConfig
│   ├── ImageConfig
│   ├── AudioConfig
│   ├── ConversationConfig
│   └── file: Path | None
├── OutputConfig (Results output)
│   └── artifact_directory: Path
├── TokenizerConfig (Tokenization)
│   └── tokenizer_name: str
└── LoadGeneratorConfig (Load parameters)
    ├── request_rate: float | None
    ├── concurrency: int | None
    ├── request_count: int
    └── request_rate_mode: RequestRateMode

ServiceConfig (Internal service configuration)
├── service_run_type: ServiceRunType
├── record_processor_service_count: int | None
└── zmq: ZMQCommunicationConfig
```

### Using Configuration

All configuration classes are Pydantic models:

```python
from aiperf.common.config import UserConfig
from aiperf.common.enums import EndpointType

# Create from defaults
user_config = UserConfig(
    endpoint=EndpointConfig(
        type=EndpointType.CHAT,
        url="http://localhost:8000/v1/chat/completions",
        model_names=["my-model"],
        streaming=True,
    ),
    loadgen=LoadGeneratorConfig(
        request_rate=10.0,
        request_count=100,
    ),
)

# Access nested config
endpoint_url = user_config.endpoint.url
request_rate = user_config.loadgen.request_rate

# Validate on construction
try:
    config = UserConfig(endpoint=invalid_endpoint)
except ValidationError as e:
    print(e)
```

### Configuration Parameters

All configuration parameters can be set via CLI:

```python
from typing import Annotated
from pydantic import Field
from aiperf.common.config.cli_parameter import (
    CLIParameter, Group, DisableCLI
)

class MyConfig(BaseConfig):
    param: Annotated[
        int,
        Field(description="My parameter"),
        CLIParameter(
            names=["--my-param"],
            group=Group.ADVANCED,  # Group in help text
        ),
    ] = 10

    internal_param: Annotated[
        str,
        DisableCLI(reason="Internal use only"),  # Hide from CLI
    ] = "internal"
```

### Configuration Validation

Use Pydantic validators for complex validation:

```python
from pydantic import model_validator

class MyConfig(BaseConfig):
    min_value: int = 1
    max_value: int = 100

    @model_validator(mode="after")
    def validate_range(self):
        if self.min_value >= self.max_value:
            raise ValueError("min_value must be less than max_value")
        return self
```

---

## Best Practices

### 1. Service Development

**DO:**
- ✅ Always call `super().__init__()` in service constructors
- ✅ Use lifecycle hooks (`@on_init`, `@on_start`, `@on_stop`)
- ✅ Handle errors gracefully and log appropriately
- ✅ Clean up resources in `@on_stop` hooks
- ✅ Use type hints for all method signatures

**DON'T:**
- ❌ Block the event loop with synchronous I/O
- ❌ Create tight loops without `await` statements
- ❌ Share mutable state between processes
- ❌ Forget to await async methods

```python
# Good
@on_init
async def _initialize(self):
    self.resource = await create_resource()

@on_stop
async def _cleanup(self):
    await self.resource.close()

# Bad
def __init__(self, ...):
    self.resource = create_resource()  # No async in __init__!
```

### 2. Factory Implementation

**DO:**
- ✅ Register with appropriate factory type
- ✅ Implement all protocol methods
- ✅ Document constructor parameters
- ✅ Handle initialization errors

**DON'T:**
- ❌ Skip required protocol methods
- ❌ Assume specific constructor parameters
- ❌ Raise exceptions in constructors (do it in `initialize()`)

```python
# Good
@InferenceClientFactory.register(EndpointType.MY_TYPE)
class MyClient:
    def __init__(self, model_endpoint: ModelEndpointInfo):
        self.model_endpoint = model_endpoint
        self.session = None  # Don't create in __init__

    async def initialize(self):
        self.session = await create_session()  # Create here

# Bad
@InferenceClientFactory.register(EndpointType.MY_TYPE)
class MyClient:
    def __init__(self, model_endpoint: ModelEndpointInfo):
        self.session = create_session()  # Bad: blocking call in __init__
```

### 3. Metric Development

**DO:**
- ✅ Use descriptive tag names
- ✅ Set appropriate flags
- ✅ Document metric computation
- ✅ Handle edge cases (empty data, missing values)
- ✅ Specify dependencies

**DON'T:**
- ❌ Forget to set `required_metrics`
- ❌ Create circular dependencies
- ❌ Compute expensive operations in tight loops
- ❌ Ignore `NoMetricValue` exceptions

```python
# Good
class MyMetric(BaseRecordMetric[int]):
    tag = "my_metric"
    required_metrics = {"dependency"}

    def _parse_record(self, record, record_metrics):
        if not record.responses:
            raise NoMetricValue("No responses")

        dependency = record_metrics["dependency"]
        return compute(record, dependency)

# Bad
class MyMetric(BaseRecordMetric[int]):
    tag = "my_metric"
    # Missing required_metrics!

    def _parse_record(self, record, record_metrics):
        # No error handling!
        return compute(record)
```

### 4. Communication Patterns

**DO:**
- ✅ Use appropriate pattern (PUB/SUB for broadcasts, REQ/REP for RPC)
- ✅ Set reasonable timeouts
- ✅ Handle communication failures
- ✅ Log message sends/receives at DEBUG level

**DON'T:**
- ❌ Use blocking calls in async context
- ❌ Create too many connections
- ❌ Ignore timeout errors
- ❌ Flood the message bus

```python
# Good
try:
    response = await self.req_client.request(
        message, timeout=10.0
    )
except asyncio.TimeoutError:
    self.error("Request timed out")
    # Handle timeout gracefully

# Bad
response = await self.req_client.request(message)  # No timeout!
# What if it never responds?
```

### 5. Error Handling

**DO:**
- ✅ Use appropriate log levels (debug, info, warning, error)
- ✅ Include context in error messages
- ✅ Use custom exceptions for specific errors
- ✅ Propagate errors appropriately

**DON'T:**
- ❌ Swallow exceptions silently
- ❌ Use bare `except:` clauses
- ❌ Log full stack traces at INFO level
- ❌ Expose sensitive data in logs

```python
# Good
try:
    result = await process_data(data)
except DataProcessingError as e:
    self.error(f"Failed to process {data.id}: {e}")
    raise
except Exception as e:
    self.exception(f"Unexpected error processing {data.id}: {e}")
    raise

# Bad
try:
    result = await process_data(data)
except:  # Bare except!
    pass  # Silently swallowed!
```

### 6. Testing

**DO:**
- ✅ Write unit tests for factories
- ✅ Test edge cases (empty data, errors)
- ✅ Use pytest fixtures
- ✅ Mock external dependencies

**DON'T:**
- ❌ Skip testing error paths
- ❌ Use real network calls in tests
- ❌ Hard-code test data

```python
# Good
@pytest.fixture
def mock_endpoint():
    return ModelEndpointInfo(
        endpoint=EndpointConfig(
            type=EndpointType.CHAT,
            url="http://test.local",
            model_names=["test-model"],
        )
    )

def test_client_creation(mock_endpoint):
    client = InferenceClientFactory.create_instance(
        EndpointType.CHAT,
        model_endpoint=mock_endpoint,
    )
    assert client is not None

def test_client_error_handling(mock_endpoint):
    with pytest.raises(ClientError):
        await client.send_invalid_request()
```

### 7. Performance

**DO:**
- ✅ Use async for I/O operations
- ✅ Batch operations when possible
- ✅ Use appropriate data structures
- ✅ Profile hot paths

**DON'T:**
- ❌ Do CPU-intensive work in async functions
- ❌ Create unnecessary copies
- ❌ Use inefficient algorithms
- ❌ Block the event loop

```python
# Good
async def process_batch(items: list):
    # Process items concurrently
    tasks = [process_item(item) for item in items]
    return await asyncio.gather(*tasks)

# Bad
async def process_batch(items: list):
    results = []
    for item in items:
        results.append(await process_item(item))  # Sequential!
    return results
```

---

## Development Workflow

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/ai-dynamo/aiperf.git
cd aiperf

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/metrics/test_ttft_metric.py

# Run with coverage
pytest --cov=aiperf --cov-report=html

# Run in parallel
pytest -n auto
```

### Code Style

AIPerf uses:
- **Black** for formatting
- **Ruff** for linting
- **MyPy** for type checking

```bash
# Format code
black aiperf/

# Lint code
ruff check aiperf/

# Type check
mypy aiperf/

# Run all checks
pre-commit run --all-files
```

### Adding New Components

**1. Create implementation file**
```bash
# Example: new metric
touch aiperf/metrics/types/my_new_metric.py
```

**2. Implement with proper registration**
```python
from aiperf.metrics import BaseRecordMetric

class MyNewMetric(BaseRecordMetric[int]):
    tag = "my_new_metric"
    # ... implementation
```

**3. Add tests**
```bash
touch tests/metrics/test_my_new_metric.py
```

**4. Test locally**
```bash
pytest tests/metrics/test_my_new_metric.py -v
```

**5. Run full test suite**
```bash
pytest
```

### Debugging

**Using Built-in Logging:**

```python
from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)

logger.debug("Detailed debugging information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
logger.exception("Exception with traceback")
```

**Increasing Log Verbosity:**

```bash
# Set log level via environment variable
export AIPERF_LOG_LEVEL=DEBUG
aiperf profile ...

# Or use dev mode
aiperf profile --dev-mode ...
```

**Using Debugger:**

```python
# Insert breakpoint
import pdb; pdb.set_trace()

# Or use Python 3.7+ breakpoint()
breakpoint()
```

### Creating Pull Requests

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes and commit**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

3. **Push and create PR**
   ```bash
   git push origin feature/my-new-feature
   # Create PR on GitHub
   ```

4. **PR Requirements**
   - ✅ All tests pass
   - ✅ Code style checks pass
   - ✅ Documentation updated
   - ✅ Changelog entry added

---

## Common Patterns Cookbook

### Pattern: Adding a New Endpoint Type

**Step 1:** Add enum value
```python
# aiperf/common/enums/endpoints_enums.py
class EndpointType(CaseInsensitiveStrEnum):
    CHAT = "chat"
    COMPLETIONS = "completions"
    MY_NEW_TYPE = "my_new_type"  # Add here
```

**Step 2:** Implement client
```python
# aiperf/clients/my_new_client.py
@InferenceClientFactory.register(EndpointType.MY_NEW_TYPE)
class MyNewClient:
    # ... implementation
```

**Step 3:** Implement request converter
```python
# aiperf/clients/my_new_converter.py
@RequestConverterFactory.register(EndpointType.MY_NEW_TYPE)
class MyNewConverter:
    # ... implementation
```

**Step 4:** Implement response extractor
```python
# aiperf/parsers/my_new_parser.py
@ResponseExtractorFactory.register(EndpointType.MY_NEW_TYPE)
class MyNewExtractor:
    # ... implementation
```

**Step 5:** Test
```bash
aiperf profile \
    --model my-model \
    --url http://localhost:8000/my-endpoint \
    --endpoint-type my_new_type
```

### Pattern: Custom Dataset Format

**Step 1:** Add enum
```python
class CustomDatasetType(CaseInsensitiveStrEnum):
    MY_FORMAT = "my_format"
```

**Step 2:** Implement loader
```python
@CustomDatasetFactory.register(CustomDatasetType.MY_FORMAT)
class MyFormatLoader:
    def __init__(self, file_path: Path, **kwargs):
        self.file_path = file_path

    def load(self) -> list[Conversation]:
        # Parse file and return conversations
        ...
```

**Step 3:** Use
```bash
aiperf profile \
    --input-file my_data.xyz \
    --custom-dataset-type my_format \
    --model my-model \
    --url http://localhost:8000
```

### Pattern: Service-to-Service Communication

```python
# Service A: Sending data
class ServiceA(BaseService):
    @on_start
    async def _start(self):
        # Create push client
        self.data_push = self.comms.create_push_client(
            "tcp://127.0.0.1:6000"
        )

        # Send data
        await self.data_push.push(
            MyDataMessage(
                service_id=self.service_id,
                data={"key": "value"},
            )
        )

# Service B: Receiving data
class ServiceB(BaseComponentService, PullClientMixin):
    def __init__(self, ...):
        super().__init__(
            ...,
            pull_client_address="tcp://127.0.0.1:6000",
            pull_client_bind=True,  # Bind to address
        )

    @on_pull_message(MessageType.MY_DATA)
    async def _handle_data(self, message: MyDataMessage):
        self.info(f"Received data: {message.data}")
```

### Pattern: Background Monitoring Task

```python
class MonitoringService(BaseService):
    @background_task(interval=10.0, immediate=True)
    async def _monitor_system(self):
        """Monitor system every 10 seconds."""
        stats = await self.collect_stats()

        if stats.memory_usage > 0.9:
            self.warning("High memory usage detected")
            await self.publish(
                AlertMessage(
                    service_id=self.service_id,
                    alert_type="high_memory",
                    severity="warning",
                )
            )
```

---

## Appendix

### Factory Quick Reference

| Factory | Register With | Protocol | Example Usage |
|---------|--------------|----------|---------------|
| `InferenceClientFactory` | `EndpointType` | `InferenceClientProtocol` | HTTP clients |
| `RequestConverterFactory` | `EndpointType` | `RequestConverterProtocol` | Request formatting |
| `ResponseExtractorFactory` | `EndpointType` | `ResponseExtractorProtocol` | Response parsing |
| `ComposerFactory` | `ComposerType` | `BaseDatasetComposer` | Dataset generation |
| `CustomDatasetFactory` | `CustomDatasetType` | `CustomDatasetLoaderProtocol` | File loaders |
| `ServiceFactory` | `ServiceType` | `ServiceProtocol` | System services |
| `RecordProcessorFactory` | `RecordProcessorType` | `RecordProcessorProtocol` | Metric processors |
| `DataExporterFactory` | `DataExporterType` | `DataExporterProtocol` | Result exporters |
| `ConsoleExporterFactory` | `ConsoleExporterType` | `ConsoleExporterProtocol` | Console output |

### Useful Resources

- **Source Code**: https://github.com/ai-dynamo/aiperf
- **Documentation**: https://docs.aiperf.ai
- **Issue Tracker**: https://github.com/ai-dynamo/aiperf/issues
- **Discord Community**: https://discord.gg/D92uqZRjCZ

### Glossary

- **Service**: Independent process managing specific functionality
- **Factory**: Pattern for creating instances based on type
- **Protocol**: Interface definition using structural typing
- **Hook**: Lifecycle event handler using decorators
- **Composer**: Generates synthetic datasets
- **Loader**: Loads datasets from files
- **Extractor**: Parses responses into structured data
- **Converter**: Formats requests for endpoints
- **Metric**: Performance measurement
- **Record**: Single request-response pair
- **Turn**: Single request in a conversation
- **Conversation**: Collection of turns in a session

---

## Summary

This guide covered:

1. **Architecture**: Service-oriented, message-driven design
2. **Patterns**: Factory, protocol, hooks, message-passing
3. **Factories**: 15+ extension points for customization
4. **Services**: Lifecycle management and communication
5. **Metrics**: Declarative, dependency-aware system
6. **Datasets**: Composers and loaders for data generation
7. **Clients**: HTTP communication with inference services
8. **Communication**: ZeroMQ patterns for IPC
9. **Configuration**: Pydantic-based, CLI-driven
10. **Best Practices**: Development guidelines and patterns

For questions or contributions, join our Discord or open an issue on GitHub!

**Happy coding! 🚀**
