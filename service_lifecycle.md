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
graph TD
    %% Common Initialization (BaseService)
    Init[Constructor] --> Initialize["initialize()\nServiceState.INITIALIZING"]
    Initialize --> SetupSignalHandlers["_setup_signal_handlers()"]
    SetupSignalHandlers --> InitComms["Initialize Communications"]
    InitComms --> CreateClients["Create Required Clients"]
    CreateClients --> RunInitHooks["Run @on_init hooks"]
    RunInitHooks --> ReadyState["ServiceState.READY"]
    ReadyState --> RunForever["run_forever()"]
    RunForever --> StartTasks["Start @aiperf_task tasks"]
    StartTasks --> RunHooks["Run @on_run hooks"]

    %% Branch after @on_run hooks
    RunHooks --> ControllerPath["BaseControllerService Path"]
    RunHooks --> ComponentPath["BaseComponentService Path"]

    %% BaseControllerService specific
    subgraph "BaseControllerService Lifecycle"
        ControllerPath --> AutoStart["_on_run() - Auto calls start()"]
        AutoStart --> Start["start()"]
        Start --> StartingState["ServiceState.STARTING"]
        StartingState --> RunStartHooks["Run @on_start hooks"]
        RunStartHooks --> RunningState["ServiceState.RUNNING"]
        RunningState --> WaitForStop["Wait for stop_event"]
    end

    %% BaseComponentService specific
    subgraph "BaseComponentService Lifecycle"
        ComponentPath --> SubscribeCommand["_on_run() - Subscribe to command topic"]
        SubscribeCommand --> RegisterService["register() - Send registration message to controller"]
        RegisterService --> HeartbeatTask["_heartbeat_task starts running"]
        HeartbeatTask --> WaitCommands["Wait for commands"]
        WaitCommands --> ProcessCommand["process_command_message()"]
        ProcessCommand -- "CommandType.START" --> CompStart["start()"]
        CompStart --> CompStartingState["ServiceState.STARTING + publish status"]
        CompStartingState --> CompRunStartHooks["Run @on_start hooks"]
        CompRunStartHooks --> CompRunningState["ServiceState.RUNNING + publish status"]
        ProcessCommand -- "CommandType.STOP" --> StopService["stop_event.set()"]
        ProcessCommand -- "CommandType.CONFIGURE" --> Configure["_configure()"]
    end

    %% Common stopping process (BaseService)
    StopEvent["Stop event is set"] --> TriggerStop["stop()"]
    TriggerStop --> StoppingState["ServiceState.STOPPING"]
    StoppingState --> RunStopHooks["Run @on_stop hooks"]
    RunStopHooks --> ShutdownComms["Shutdown communications"]
    ShutdownComms --> CancelTasks["Cancel all registered tasks"]
    CancelTasks --> RunCleanupHooks["Run @on_cleanup hooks"]
    RunCleanupHooks --> StoppedState["ServiceState.STOPPED"]

    %% Connect the Controller and Component back to the common stopping process
    WaitForStop --> StopEvent
    StopService --> StopEvent

    %% Visual styling
    classDef state fill:#f9f,stroke:#333,stroke-width:2px,color:#000;
    classDef hook fill:#bbf,stroke:#333,stroke-width:2px,color:#000,font-weight:bold;
    classDef controller fill:#fbb,stroke:#333,stroke-width:2px,color:#000;
    classDef component fill:#bfb,stroke:#333,stroke-width:2px,color:#000;
    classDef path fill:#fcf,stroke:#333,stroke-width:1px,color:#000,font-style:italic;

    class Init,Initialize,ReadyState,StartingState,RunningState,StoppingState,StoppedState,CompStartingState,CompRunningState state;
    class RunInitHooks,RunHooks,RunStartHooks,RunStopHooks,RunCleanupHooks,CompRunStartHooks hook;
    class AutoStart,WaitForStop controller;
    class SubscribeCommand,RegisterService,WaitCommands,ProcessCommand,HeartbeatTask component;
    class ControllerPath,ComponentPath path;
```
