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
```mermaid
sequenceDiagram
    participant SC as System Controller
    participant ZMQ as ZeroMQ Clients
    participant CS as Component Service

    Note over SC,CS: Initialization Phase

    SC->>SC: initialize()
    SC->>ZMQ: Subscribe to Topic.REGISTRATION, Topic.HEARTBEAT, Topic.STATUS

    CS->>CS: initialize()
    CS->>ZMQ: Subscribe to Topic.COMMAND

    Note over SC,CS: Registration
    CS->>ZMQ: Publish Registration (Topic.REGISTRATION)
    ZMQ->>SC: Forward Registration Message
    SC->>SC: Process Registration
    SC->>SC: Store Component Service details
    CS->>ZMQ: Publish (Topic.STATUS, READ)
    ZMQ->>SC: Forward Status Message

    Note over SC,CS: Configuration (if needed)
    SC->>ZMQ: Publish CONFIGURE Command (Topic.COMMAND)
    ZMQ->>CS: Forward Command Message
    CS->>CS: process_command_message()
    CS->>CS: _configure()

    Note over SC,CS: Start Command
    SC->>ZMQ: Publish START Command (Topic.COMMAND)
    ZMQ->>CS: Forward Command Message
    CS->>CS: process_command_message()
    CS->>CS: start()
    CS->>ZMQ: Publish (Topic.STATUS, STARTING)
    ZMQ->>SC: Forward Status Message
    CS->>CS: Run @on_start hooks
    CS->>ZMQ: Publish (Topic.STATUS, RUNNING)
    ZMQ->>SC: Forward Status Message

    Note over SC,CS: Operational Phase

    loop Heartbeat Interval
        CS->>ZMQ: Publish Heartbeat (Topic.HEARTBEAT)
        ZMQ->>SC: Forward Heartbeat Message
        SC->>SC: Update Service Status
    end

    Note over SC,CS: Shutdown Phase
    SC->>ZMQ: Publish STOP Command (Topic.COMMAND)
    ZMQ->>CS: Forward Command Message
    CS->>CS: process_command_message()
    CS->>CS: Set stop_event
    CS->>CS: Set state to STOPPING
    CS->>ZMQ: Publish Status Update (Topic.STATUS, STOPPING)
    ZMQ->>SC: Forward Status Message
    CS->>CS: Run @on_stop hooks
    CS->>CS: Shutdown communications
    CS->>CS: Cancel all registered tasks
    CS->>CS: Run @on_cleanup hooks
    CS->>CS: Set state to STOPPED
```
