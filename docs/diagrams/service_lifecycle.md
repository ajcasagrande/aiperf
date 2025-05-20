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
    %% Common base service lifecycle
    Init[Constructor] --> Initialize["initialize()\nServiceState.INITIALIZING"]
    Initialize --> SetupSignalHandlers["_setup_signal_handlers()"]
    SetupSignalHandlers --> InitComms["Initialize Communications"]
    InitComms --> RunInitHooks["Run @on_init hooks"]
    RunInitHooks --> Ready["ServiceState.READY"]
    Ready --> RunForever["run_forever()"]
    RunForever --> RunHooks["Run @on_run hooks"]

    %% BaseControllerService specific
    subgraph "BaseControllerService"
        RunHooks --> AutoStart["_on_run() - Automatically calls start()"]
        AutoStart --> Start["start()"]
        Start --> StartingState["ServiceState.STARTING"]
        StartingState --> RunStartHooks["Run @on_start hooks"]
        RunStartHooks --> RunningState["ServiceState.RUNNING"]
    end

    %% BaseComponentService specific
    subgraph "BaseComponentService"
        RunHooks --> SubscribeCommand["_on_run() - Subscribe to command topic"]
        SubscribeCommand --> RegisterService["register() - Send registration message"]
        RegisterService --> WaitCommands["Wait for commands"]
        WaitCommands --> ProcessCommand["process_command_message()"]
        ProcessCommand -- "CommandType.START" --> Start
        ProcessCommand -- "CommandType.STOP" --> StopService["stop()"]
        ProcessCommand -- "CommandType.CONFIGURE" --> Configure["_configure()"]
    end

    %% Common stopping process
    StopEvent["Stop event is set"] --> StopService
    StopService --> StoppingState["ServiceState.STOPPING"]
    StoppingState --> RunStopHooks["Run @on_stop hooks"]
    RunStopHooks --> ShutdownComms["Shutdown communications"]
    ShutdownComms --> CancelTasks["Cancel all registered tasks"]
    CancelTasks --> RunCleanupHooks["Run @on_cleanup hooks"]
    RunCleanupHooks --> StoppedState["ServiceState.STOPPED"]

    %% Visual styling
    classDef state fill:#f9f,stroke:#333,stroke-width:2px;
    classDef hook fill:#bbf,stroke:#333,stroke-width:2px;
    classDef controller fill:#fbb,stroke:#333,stroke-width:2px;
    classDef component fill:#bfb,stroke:#333,stroke-width:2px;

    class Init,Initialize,Ready,StartingState,RunningState,StoppingState,StoppedState state;
    class RunInitHooks,RunHooks,RunStartHooks,RunStopHooks,RunCleanupHooks hook;
    class AutoStart controller;
    class SubscribeCommand,RegisterService,WaitCommands,ProcessCommand component;
```
