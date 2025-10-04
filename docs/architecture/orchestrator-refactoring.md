<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Orchestrator Refactoring: Kubernetes-Friendly Architecture

## Overview

This document describes the refactoring of AIPerf's architecture to separate the CLI orchestration layer from the system controller, making the system more suitable for Kubernetes deployments.

## Architecture Changes

### Before: Monolithic System Controller

```
CLI → run_system_controller() → SystemController
                                  ├── UI Management
                                  ├── Service Management
                                  ├── Benchmark Lifecycle
                                  ├── Results Export
                                  └── Process Exit
```

**Issues:**
- SystemController had too many responsibilities
- UI and display logic tightly coupled with service management
- Difficult to deploy as separate services in Kubernetes
- Hard to run controller independently without UI

### After: Separated Orchestrator and Controller

```
CLI → run_aiperf_system()
       ├── CLIOrchestrator (Local/UI Layer)
       │   ├── UI Management
       │   ├── Results Monitoring
       │   ├── Results Export/Display
       │   └── Process Exit
       │
       └── SystemController (Service Layer)
           ├── Service Management
           ├── Benchmark Lifecycle
           └── Health Monitoring
```

## Component Responsibilities

### CLIOrchestrator (`aiperf/orchestrator/cli_orchestrator.py`)

**Primary Responsibilities:**
- Create and manage the UI (dashboard, tqdm, no-ui)
- Monitor system status via message bus
- Receive and aggregate results (benchmark + telemetry)
- Export results to files (CSV, JSON)
- Display results to console
- Coordinate shutdown and exit

**Key Features:**
- Subscribes to message bus for results
- Manages UI lifecycle independently
- Handles all console output and file exports
- Determines process exit code

### SystemController (`aiperf/controller/system_controller.py`)

**Primary Responsibilities:**
- Manage service lifecycle (start, stop, configure)
- Handle service registration and health monitoring
- Coordinate benchmark execution phases
- Manage worker spawning and shutdown
- Publish results to message bus

**Key Features:**
- No UI dependencies
- Can run as standalone service
- Communicates via ZMQ message bus
- Kubernetes-friendly (no process exit control)

### Runner (`aiperf/orchestrator/runner.py`)

**Primary Responsibilities:**
- Bootstrap both orchestrator and controller
- Coordinate initialization and startup
- Transfer state between components
- Handle process exit

## Communication Flow

Both components communicate via the existing ZMQ message bus:

```
Services → Message Bus → SystemController
                      ↓
                      → CLIOrchestrator
                      ↓
                      → UI
```

**Key Messages:**
- `PROCESS_RECORDS_RESULT`: Benchmark results from RecordsManager
- `PROCESS_TELEMETRY_RESULT`: GPU telemetry from TelemetryManager
- `TELEMETRY_STATUS`: Telemetry availability status
- `STATUS`: Service lifecycle status updates
- `HEARTBEAT`: Service health indicators

## Benefits for Kubernetes

### 1. Service Separation
- **SystemController** can run as a Kubernetes pod without UI dependencies
- **CLIOrchestrator** can run locally or in a separate pod
- Each component can be scaled independently

### 2. Remote Monitoring
- CLI orchestrator can connect to remote system controller
- Multiple orchestrators can monitor same benchmark
- UI can be detached and reattached

### 3. Clean Shutdown
- SystemController no longer calls `os._exit()`
- Kubernetes can manage pod lifecycle cleanly
- Graceful shutdown via message bus

### 4. Flexible Deployment

**Scenario 1: Local Development (Current)**
```
Local Machine: CLIOrchestrator + SystemController
```

**Scenario 2: Kubernetes Deployment (Future)**
```
Kubernetes Pod: SystemController (headless)
Local Machine: CLIOrchestrator (connects remotely)
```

**Scenario 3: Full Kubernetes (Future)**
```
Kubernetes Pod 1: SystemController
Kubernetes Pod 2: CLIOrchestrator (web UI)
```

## Migration Path

### Phase 1: In-Process Separation ✅ (Current)
- Orchestrator and controller run in same process
- Share message bus and state
- Maintains backward compatibility

### Phase 2: Remote Communication (Future)
- Add remote ZMQ proxy configuration
- Enable orchestrator to connect to remote controller
- Support distributed deployment

### Phase 3: Kubernetes Native (Future)
- Helm charts for deployment
- Service discovery and configuration
- Health checks and auto-scaling

## Files Modified

### New Files:
- `aiperf/orchestrator/__init__.py` - Module exports
- `aiperf/orchestrator/cli_orchestrator.py` - CLI orchestration logic
- `aiperf/orchestrator/runner.py` - Bootstrap coordinator

### Modified Files:
- `aiperf/cli.py` - Updated to use new runner
- `aiperf/controller/system_controller.py` - Removed UI and export logic

### Preserved Files:
- `aiperf/cli_runner.py` - Kept for backward compatibility (deprecated)
- All UI implementations - No changes needed
- All service managers - No changes needed

## Testing

The refactored architecture maintains full backward compatibility:

```bash
# All existing commands work unchanged
aiperf profile --endpoint http://localhost:8000 --model gpt-4 ...
```

**Test Coverage Needed:**
1. Local execution (all UI modes)
2. Service lifecycle management
3. Results export and display
4. Error handling and shutdown
5. Kubernetes deployment (future)

## Future Enhancements

### 1. Remote Orchestrator
```python
# Connect to remote system controller
orchestrator = CLIOrchestrator(
    remote_endpoint="tcp://controller-service:5555"
)
```

### 2. Multiple Orchestrators
- Multiple CLIs monitoring same benchmark
- Web UI + terminal UI simultaneously
- Real-time metric streaming

### 3. Kubernetes Integration
- Helm chart for deployment
- ConfigMap for configuration
- ServiceMonitor for metrics

### 4. API Server Mode
- SystemController exposes REST API
- Orchestrator uses HTTP instead of ZMQ
- Better for cloud deployments

## Backward Compatibility

All existing code continues to work:
- ✅ CLI commands unchanged
- ✅ Configuration files unchanged
- ✅ UI implementations unchanged
- ✅ Service management unchanged
- ✅ Message protocols unchanged

The refactoring is an internal architectural improvement with no breaking changes.
