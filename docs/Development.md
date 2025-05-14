<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
-->
# Developers Guide
Execute the following commands to set up your development environment for `aiperf`.
Make sure you are in the root directory of the `aiperf` repository.

## Development Environment
- Install uv
https://docs.astral.sh/uv/getting-started/installation/
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

- Create virtual env
```bash
uv venv
```

- Activate venv
```bash
source .venv/bin/activate
```

- Install `aiperf` package in editable development mode
```bash
uv pip install -e ".[dev]"
```

- Run `aiperf` with the process manager backend
```bash
aiperf --run-type process
```
Press `Ctrl-C` to stop the process

- Run `aiperf` with the Kubernetes backend
```bash
aiperf --run-type k8s
```
Press `Ctrl-C` to stop the process

- Run `aiperf` with `--help` to see available commands
```bash
aiperf --help
```

## Code Overview

### Project Structure

```
aiperf/
├── aiperf/              # Main python package
│   ├── app/                 # Application components
│   ├── cli.py               # Command line interface
│   ├── common/              # Shared utilities and models
│   │   ├── bootstrap.py        # Service bootstrap functionality
│   │   ├── comms/              # Communication components
│   │   ├── config/             # Configuration management
│   │   ├── enums.py            # Enum definitions
│   │   ├── exceptions/         # Custom exceptions
│   │   ├── models/             # Pydantic data models
│   │   │   ├── messages.py         # Message definitions
│   │   │   └── payloads.py         # Message payload definitions
│   │   ├── service/            # Service components
│   │   │   ├── base.py             # Base service implementation
│   │   │   ├── component.py        # Component base classes
│   │   │   └── controller.py       # Controller base classes
│   │   └── utils.py             # Utility functions
│   └── services/            # System services
│       ├── dataset_manager/        # Handles dataset operations
│       ├── post_processor_manager/ # Processes results
│       ├── records_manager/        # Manages test records
│       ├── system_controller/      # Controls system operation
│       ├── timing_manager/         # Handles timing and credits
│       ├── worker/                 # Executes benchmarks
│       └── worker_manager/         # Manages worker processes
├── docs/                # Documentation
├── tests/               # Test suite
├── pyproject.toml       # Project configuration
├── Makefile             # Build and automation scripts
└── README.md            # Project readme
```

### Core Components
> This comes from the AIPerf Design Document

AIPerf implements a distributed microservices architecture with the following key components:

- **System Controller**: Primary responsibility is to orchestrate the system. It will ensure all blocks are ready and healthy. It will also help orchestrating graceful shutdowns. This is the component that will contain the methods users can interact with.
- **Dataset Manager**: Primary responsibility is to manage the data: generation or acquisition. For  synthetic generation, it contains the code to generate the prompts or tokens. It will have an API for dataset acquisition of a dataset if available in a remote repository or database.

- **Worker Manager**: Primary responsibility is to pull data from the dataset manager after receiving the timing credit from the timing manager. It will then push the request data to the worker to issue to the request.
- **Worker**: Primarily responsible for converting the data into the appropriate format for the interface being used by the server. Also responsible for managing the conversation between turns.

- **Timing Manager**: Primary responsibility is to generate the schedule and issuing timing credits for requests.

- **Records Manager**: Primarily responsible for holding the results returned from the workers.

- **Post-Processor Manager**: Primarily responsible for iterating over the records to generate metrics and other conclusions from the records.


#### Communication System

Services communicate using a message-based system with the following components:

- **Topics**: Categorized channels for message distribution (commands, status, data, etc.)
- **Messages**: Strongly-typed data structures for inter-service communication
- **Service States**: Lifecycle states that services transition through (initializing, running, stopping, etc.)

#### Command Line Interface

The CLI (`aiperf/cli.py`) provides the entry point to the system with options including:

- `--config`: Path to configuration file
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--run-type`: Process manager backend to use (process, k8s)



### Service Inheritance Model

AIPerf uses an inheritance-based architecture where all system services inherit from a common `ServiceBase` abstract class. This approach provides a consistent interface and shared functionality across services.

#### Base Service Responsibilities

The `ServiceBase` class (`aiperf/common/service/base.py`) provides automatically for all services:

- **Lifecycle Management**: Standard initialize/run/stop/cleanup methods
- **State Transitions**: Manages service state changes (INITIALIZING → RUNNING → STOPPING → STOPPED)
- **Communication**: Methods for publishing messages and subscribing to topics
- **Heartbeat**: Automatic heartbeat generation for service health monitoring

#### Service Implementation Requirements

When implementing a new service that inherits from `ServiceBase`, you must:

1. **Implement Abstract Methods**:
   - `_initialize()`: Set up service-specific resources
   - `_on_start()`: Main service logic
   - `_on_stop()`: Handle graceful shutdown
   - `_cleanup()`: Release resources

2. **Configuration**:
   - Define service-specific configuration needs
   - Pass configuration to the base class constructor

#### Example Service Implementation

Here's a simplified example of a service implementation:

```python
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import Topic, ClientType, ServiceType
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service.base import ServiceBase


class ExampleService(ServiceBase):
    @property
    def service_type(self) -> ServiceType:
        return ServiceType.EXAMPLE_SERVICE

    def __init__(self, service_config: ServiceConfig, service_id: str = None) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.my_resource = None

    async def _initialize(self) -> None:
        """Initialize service-specific resources."""
        await self._base_init()
        self.logger.debug("Initializing Example Service")
        # Subscribe to required topics
        success = await self.communication.subscribe(
            ClientType.COMPONENT_SUB, Topic.COMMAND, self._handle_command
        )
        # Initialize resources
        self.my_resource = SomeResource()

    async def _on_start(self) -> None:
        """Main service logic."""
        self.logger.debug("Running Example Service")
        # Implement your service's main logic here
        # This method should typically set up ongoing tasks or loops

    async def _on_stop(self) -> None:
        """Handle graceful shutdown."""
        self.logger.debug("Stopping Example Service")
        # Cancel any ongoing tasks
        # Prepare for cleanup

    async def _cleanup(self) -> None:
        """Release resources."""
        self.logger.debug("Cleaning up Example Service")
        # Release any resources
        if self.my_resource:
            await self.my_resource.close()

    async def _handle_command(self, message: BaseMessage) -> None:
        """Handle command messages."""
        # Implement command handling logic
```

#### Using the Service

To instantiate and run a service:

```python
from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config.service_config import ServiceConfig

# Create a service configuration
config = ServiceConfig(service_run_type="process")

# Bootstrap and run the service
bootstrap_and_run_service(ExampleService, service_config=config)
```

The `bootstrap_and_run_service` function handles:
1. Setting up the event loop (using uvloop)
2. Creating an instance of your service
3. Running the service's lifecycle methods
4. Handling graceful shutdown

This inheritance model ensures consistent behavior across all services while allowing for service-specific customization.

