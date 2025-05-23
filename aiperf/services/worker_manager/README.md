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
# Dealer Router Worker Manager

This module implements a worker manager that utilizes ZeroMQ's Dealer-Router pattern to distribute tasks to multiple worker processes efficiently.

## Overview

The `DealerRouterWorkerManager` uses the following components:

1. **DealerRouterBroker**: A broker that connects a Router socket (for clients) to a Dealer socket (for workers)
2. **DealerWorker**: A worker process that connects to the Dealer socket and processes tasks
3. **Multiprocessing**: For spawning worker processes
4. **Asyncio**: For asynchronous task processing

This architecture allows for efficient load balancing across multiple worker processes, handling high-throughput scenarios with dynamic scaling.

## Architecture

```
                                 ┌─────────────┐
                                 │             │
                      ┌─────────►│  Worker 1   │
                      │          │             │
                      │          └─────────────┘
┌─────────┐      ┌────┴─────┐    ┌─────────────┐
│         │      │          │    │             │
│ Clients ├─────►│  Broker  ├───►│  Worker 2   │
│         │      │          │    │             │
└─────────┘      └────┬─────┘    └─────────────┘
                      │          ┌─────────────┐
                      │          │             │
                      └─────────►│  Worker N   │
                                 │             │
                                 └─────────────┘
```

- **Clients** connect to the **Router** socket
- The **Broker** routes messages between Clients and Workers
- **Workers** connect to the **Dealer** socket
- The pattern automatically load-balances requests across available workers

## Usage

### Starting the Worker Manager

```python
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceRunType
from aiperf.services.worker_manager.dealer_router_worker_manager import DealerRouterWorkerManager

# Create configuration
config = ServiceConfig(service_run_type=ServiceRunType.MULTIPROCESSING)

# Set dealer-router addresses as attributes
setattr(config, "worker_count", 4)  # Number of worker processes
setattr(config, "router_address", "tcp://127.0.0.1:5555")
setattr(config, "dealer_address", "tcp://127.0.0.1:5556")
setattr(config, "control_address", "tcp://127.0.0.1:5557")
setattr(config, "capture_address", "tcp://127.0.0.1:5558")

# Create and start worker manager
async def start_manager():
    worker_manager = DealerRouterWorkerManager(config)
    await worker_manager.initialize()
    await worker_manager.start()

    # Your application logic here
    # ...

    # When done:
    await worker_manager.stop()
    await worker_manager.cleanup()

# Run the manager
import asyncio
asyncio.run(start_manager())
```

### Connecting a Client

```python
import zmq.asyncio
import json

async def send_request(router_address, request_data):
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(router_address)

    # Send request
    message = json.dumps(request_data).encode("utf-8")
    await socket.send(message)

    # Wait for response
    response = await socket.recv()
    response_data = json.loads(response.decode("utf-8"))

    # Clean up
    socket.close()

    return response_data

# Example usage
request = {
    "command": "process",
    "data": {
        "task_number": 1,
        "payload": "Task data"
    }
}

response = await send_request("tcp://127.0.0.1:5555", request)
print(f"Response: {response}")
```

## Examples

See the following example scripts:

1. `example_dealer_router.py` - Shows how to use the DealerRouterWorkerManager
2. `simple_dealer_router_test.py` - Simpler implementation to demonstrate the ZeroMQ pattern

## Benefits

- **Efficient Load Balancing**: Automatically distributes tasks across available workers
- **Scalability**: Easily scales to handle more load by adding more worker processes
- **Reliability**: Robust message delivery with automatic reconnection handling
- **Performance**: ZeroMQ provides high-throughput, low-latency messaging
- **Isolation**: Workers run in separate processes for stability and resource isolation
