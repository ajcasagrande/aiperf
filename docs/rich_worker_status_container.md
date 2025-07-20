<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# WorkerDashboard

The `WorkerDashboard` is a new Textual container that encapsulates the existing Rich workers dashboard functionality. This container provides a modern, interactive interface for monitoring worker status in the AIPerf system.

## Features

- **Complete Rich Dashboard Functionality**: Replicates all features from the Rich `WorkerStatusElement`
- **Real-time Updates**: Displays live worker status information with automatic refresh
- **Status Classification**: Categorizes workers as healthy, high load, error, idle, or stale
- **Summary Statistics**: Shows overview counts for each worker status category
- **Detailed Worker Table**: Displays comprehensive information for each worker
- **Configurable Thresholds**: Customizable limits for status determination
- **Pydantic Models**: Uses type-safe models for all data structures

## Components

### Main Container
- `WorkerDashboard`: The main container that encapsulates all functionality

### Data Models
- `WorkerStatus`: Enum for worker status classifications
- `WorkerStatusSummary`: Summary statistics for worker status counts
- `WorkerStatusData`: Individual worker status information

### Widgets
- `WorkerStatusTable`: Table widget displaying worker details
- `WorkerStatusSummaryWidget`: Summary widget showing status counts

## Usage

### Basic Usage

```python
from aiperf.ui.textual.rich_worker_status_container import WorkerDashboard

# Create the container
container = WorkerDashboard()

# Add to your Textual app
class MyApp(App):
    def compose(self) -> ComposeResult:
        yield container
```

### With Custom Thresholds

```python
container = WorkerDashboard(
    stale_threshold=60.0,        # Worker is stale after 60 seconds
    error_rate_threshold=0.2,    # Error status at 20% failure rate
    high_cpu_threshold=85.0,     # High load status at 85% CPU usage
)
```

### Updating Worker Data

```python
# Update with worker health data
worker_health = {
    "worker-001": worker_health_message_1,
    "worker-002": worker_health_message_2,
}
container.update_worker_health(worker_health)

# Update individual worker last seen time
container.update_worker_last_seen("worker-001", time.time())
```

### Getting Status Information

```python
# Get current worker count
count = container.get_worker_count()

# Get status summary
summary = container.get_summary()
print(f"Healthy: {summary.healthy_count}")
print(f"Errors: {summary.error_count}")
print(f"Total: {summary.total_count}")
```

## Worker Status Classification

The container classifies workers into five categories:

1. **Healthy**: Normal operation with low error rates and CPU usage
2. **High Load**: CPU usage above the configured threshold (default: 75%)
3. **Error**: Error rate above the configured threshold (default: 10%)
4. **Idle**: No tasks have been processed
5. **Stale**: No updates received within the configured time (default: 30 seconds)

## Table Columns

The worker table displays the following information:

- **Worker ID**: Unique identifier for the worker
- **Status**: Current worker status with color coding
- **Active**: Number of tasks currently in progress
- **Completed**: Number of successfully completed tasks
- **Failed**: Number of failed tasks
- **CPU**: Current CPU usage percentage
- **Memory**: Current memory usage (formatted as MB/GB)
- **Read**: I/O read statistics (formatted)
- **Write**: I/O write statistics (formatted)

## Example

See `examples/rich_worker_status_container_example.py` for a complete working example that demonstrates:

- Creating sample worker data
- Real-time updates
- Different worker status scenarios
- Interactive controls

## Integration with Existing Systems

The container is designed to integrate seamlessly with the existing AIPerf Textual UI system. It can be used as a drop-in replacement for the Rich worker dashboard while maintaining all functionality.

## Testing

Comprehensive tests are available in `tests/ui/textual/test_rich_worker_status_container.py` covering:

- Component initialization
- Status determination logic
- Data processing
- Widget behavior
- Integration testing

## Key Benefits

1. **Consistency**: Provides the same functionality as the Rich version
2. **Modern UI**: Built with Textual for better interactivity
3. **Type Safety**: Uses Pydantic models for robust data handling
4. **Extensibility**: Easy to customize and extend
5. **Performance**: Efficient updates and rendering
6. **Maintainability**: Clean, well-structured code following best practices
