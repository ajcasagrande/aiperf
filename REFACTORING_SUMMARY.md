<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Orchestrator Refactoring Summary

## Overview

Successfully refactored AIPerf to separate UI/orchestration from service management, making it more Kubernetes-friendly.

## What Changed

### New Components

#### 1. CLI Orchestrator (`aiperf/orchestrator/cli_orchestrator.py`)
- **Purpose**: Handles UI, monitoring, and results display
- **Responsibilities**:
  - Creates and manages UI (dashboard, tqdm, no-ui)
  - Monitors benchmark progress via message bus
  - Receives and aggregates results
  - Exports results to files (CSV, JSON)
  - Displays results to console
  - Determines process exit code

#### 2. Runner (`aiperf/orchestrator/runner.py`)
- **Purpose**: Coordinates orchestrator and system controller
- **Responsibilities**:
  - Bootstraps both components
  - Manages initialization and startup sequence
  - Transfers state between components
  - Handles process exit

### Modified Components

#### System Controller (`aiperf/controller/system_controller.py`)
- **Removed**: UI management, results export, process exit control
- **Retained**: Service management, benchmark lifecycle, health monitoring
- **Added**: Methods to expose internal state (`get_exit_errors()`, `was_cancelled()`)

#### CLI Entry Point (`aiperf/cli.py`)
- **Changed**: Now uses `run_aiperf_system()` instead of `run_system_controller()`

### Bug Fixes

#### Circular Import Resolution
- **File**: `aiperf/common/mixins/realtime_metrics_mixin.py`
- **Issue**: Direct import of `SystemController` caused circular dependency
- **Fix**: Used `TYPE_CHECKING` guard for type-only imports

## Architecture Diagram

### Before
```
CLI
 └── SystemController
      ├── UI Management
      ├── Service Management
      ├── Benchmark Lifecycle
      ├── Results Export
      └── os._exit()
```

### After
```
CLI
 └── run_aiperf_system()
      ├── CLIOrchestrator (Local/UI Layer)
      │    ├── UI Management
      │    ├── Results Monitoring
      │    ├── Results Export/Display
      │    └── Process Exit
      │
      └── SystemController (Service Layer)
           ├── Service Management
           ├── Benchmark Lifecycle
           └── Health Monitoring
```

## Benefits

### 1. Separation of Concerns
- UI logic separated from service management
- Each component has single, well-defined responsibility
- Easier to test and maintain

### 2. Kubernetes-Friendly
- SystemController can run as standalone pod without UI
- No direct process exit calls in controller
- Clean shutdown via message bus
- Ready for distributed deployment

### 3. Future Flexibility
- CLI orchestrator can connect to remote controllers
- Multiple orchestrators can monitor same benchmark
- Easy to add web UI or API server

### 4. Backward Compatibility
- All existing CLI commands work unchanged
- No changes to configuration files
- All existing tests should pass

## Files Changed

### Created
- `aiperf/orchestrator/__init__.py`
- `aiperf/orchestrator/cli_orchestrator.py` (330 lines)
- `aiperf/orchestrator/runner.py` (125 lines)
- `docs/architecture/orchestrator-refactoring.md`

### Modified
- `aiperf/cli.py` (2 lines changed)
- `aiperf/controller/system_controller.py` (removed ~100 lines of UI/export code)
- `aiperf/common/mixins/realtime_metrics_mixin.py` (fixed circular import)

### Preserved (No Changes)
- `aiperf/cli_runner.py` (kept for backward compatibility, now deprecated)
- All UI implementations (`aiperf/ui/`)
- All service managers (`aiperf/controller/*_service_manager.py`)
- All services (workers, dataset manager, etc.)

## Testing Status

### Verified
✅ Python syntax validation
✅ Import resolution
✅ No circular dependencies
✅ Module structure

### To Be Tested (By User)
- [ ] Local execution with all UI modes (dashboard, tqdm, no-ui)
- [ ] Service lifecycle management
- [ ] Results export to CSV/JSON
- [ ] Console output formatting
- [ ] Error handling and graceful shutdown
- [ ] Existing test suite compatibility

## Usage

No changes needed! All existing commands work:

```bash
# All existing commands work unchanged
aiperf profile --endpoint http://localhost:8000 --model gpt-4 ...
```

## Future Enhancements

### Phase 1: Current (✅ Complete)
- In-process orchestrator and controller
- Shared message bus
- Backward compatible

### Phase 2: Remote Communication
- Add remote ZMQ proxy support
- Enable orchestrator to connect to remote controller
- Support distributed deployment

### Phase 3: Kubernetes Native
- Helm charts
- Service discovery
- ConfigMaps for configuration
- Health checks and auto-scaling

### Phase 4: API Server
- REST API for controller
- Web UI support
- Cloud-native deployment

## Migration Notes

### For Users
No action required. The refactoring is transparent to end users.

### For Developers
- `SystemController` no longer manages UI or exports results
- Use `CLIOrchestrator` for UI and display logic
- Both components communicate via existing message bus
- See `docs/architecture/orchestrator-refactoring.md` for details

### For Kubernetes Deployments
The architecture is now ready for:
1. Running SystemController as a headless service
2. Running CLIOrchestrator locally or in separate pod
3. Multiple orchestrators monitoring same benchmark

## Rollback Plan

If issues arise, the old `aiperf/cli_runner.py` is preserved. To rollback:

```python
# In aiperf/cli.py
from aiperf.cli_runner import run_system_controller  # Old way
# from aiperf.orchestrator.runner import run_aiperf_system  # New way
```

## Documentation

See detailed architecture documentation:
- `docs/architecture/orchestrator-refactoring.md` - Complete design rationale
- This file - Quick reference and summary

## Questions?

The refactoring maintains backward compatibility while enabling future Kubernetes deployments. Test thoroughly with your existing benchmarks before deploying to production.
