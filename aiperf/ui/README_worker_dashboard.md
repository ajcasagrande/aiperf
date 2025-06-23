<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Worker Dashboard Component

The Worker Dashboard is a new component that displays real-time status information for all workers in the AIPerf system. It provides a visual overview of worker health, performance metrics, and task completion status.

## Features

- **Real-time Worker Status**: Shows the current status of each worker (Healthy, High Load, Error, Idle, Stale)
- **Performance Metrics**: Displays CPU usage, memory consumption, and network connections
- **Task Tracking**: Shows completed tasks, failed tasks, and total tasks for each worker
- **Process Information**: Displays PID, uptime, and CPU core assignment
- **Visual Status Indicators**: Color-coded borders and status dots for quick visual assessment
- **Summary Statistics**: Provides an overview of total workers, healthy workers, and workers with issues

## Components

### WorkerStatusCard
Individual worker status card that displays metrics for a single worker.

**Key Metrics Displayed:**
- Status (Healthy, High Load, Error, Idle, Stale)
- Task completion (completed/total)
- CPU usage percentage
- Memory usage in MiB
- Uptime in human-readable format
- Process ID
- Error count

### WorkerDashboard
Main dashboard container that manages multiple worker status cards.

**Features:**
- Summary statistics at the top
- Scrollable grid of worker cards
- Automatic addition of new workers
- Periodic updates to detect stale workers

### WorkerDashboardMixin
Mixin class that provides worker health monitoring functionality to UI components.

## Integration with Textual UI

The worker dashboard is integrated into the main AIPerf textual UI as a separate tab:

1. **Performance Dashboard Tab**: Original performance metrics (press `1` to switch)
2. **Worker Status Tab**: New worker status dashboard (press `2` to switch)

## Usage

### Basic Usage

```python
from aiperf.ui.worker_dashboard import WorkerDashboard, WorkerDashboardMixin

# Create a dashboard widget
worker_dashboard = WorkerDashboard()

# Use the mixin in your UI class
class MyUIClass(WorkerDashboardMixin):
    def __init__(self):
        super().__init__()
        self.dashboard = self.get_worker_dashboard()

    def handle_worker_health(self, message: WorkerHealthMessage):
        self.update_worker_health(message)
```

### Integration with Services

```python
from aiperf.ui.worker_dashboard import WorkerDashboardService

# Create a service that subscribes to worker health messages
class MyService(BaseComponentService, WorkerDashboardMixin):

    @on_init
    async def _initialize(self):
        # Subscribe to worker health messages
        await self.comms.subscribe(Topic.WORKER_HEALTH, self._on_worker_health)

    async def _on_worker_health(self, message: WorkerHealthMessage):
        # Update the dashboard
        self.update_worker_health(message)
```

## Worker Status Classification

Workers are classified into the following status categories:

- **Healthy**: Normal operation, low error rate, reasonable CPU usage
- **High Load**: CPU usage > 90%
- **Error**: Error rate > 10%
- **Idle**: No tasks processed yet
- **Stale**: No health updates received for >30 seconds

## Color Coding

- **Green Border**: Healthy workers
- **Yellow Border**: Workers with warnings (high load)
- **Red Border**: Workers with errors
- **Gray Border**: Stale workers (no recent updates)

## UI Navigation

- **Tab 1**: Performance Dashboard (main metrics)
- **Tab 2**: Worker Status (worker health)
- **q**: Quit application
- **Ctrl+C**: Force quit

## Demo

Run the demo script to see the worker dashboard in action:

```bash
python -m aiperf.ui.worker_dashboard_demo
```

This will simulate worker health messages and display the dashboard output.

## Architecture

The worker dashboard follows a clean separation of concerns:

1. **WorkerStatusCard**: Individual worker display
2. **WorkerDashboard**: Collection of worker cards
3. **WorkerDashboardMixin**: Integration layer for UI components
4. **WorkerHealthService**: Service layer for message subscription

## Extending

To add new metrics or modify the display:

1. Update the `WorkerStatusCard` to add new fields
2. Modify the `update_health()` method to handle new data
3. Adjust the CSS styling as needed
4. Update the status classification logic in `check_stale()` method

## Dependencies

- Textual (for UI components)
- AIPerf common models and services
- Worker health message types