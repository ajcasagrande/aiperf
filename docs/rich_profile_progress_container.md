<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# RichProfileProgressContainer

The `RichProfileProgressContainer` is a new Textual container that encapsulates the existing Rich profile progress dashboard functionality. This container provides a modern, interactive interface for monitoring profile run progress in the AIPerf system.

## Features

- **Complete Rich Dashboard Functionality**: Replicates all features from the Rich `ProfileProgressElement`
- **Real-time Progress Tracking**: Displays live profile run status and progress information
- **Phase-based Monitoring**: Shows progress for different credit phases (warmup, steady state, cooldown)
- **Comprehensive Statistics**: Displays request rates, processing statistics, and error tracking
- **Worker Integration**: Shows active worker counts and task distribution
- **Phase Overview**: Optional table showing all phases with their status and progress
- **Configurable Display**: Toggle phase overview on/off
- **Pydantic Models**: Uses type-safe models for all data structures

## Components

### Main Container
- `RichProfileProgressContainer`: The main container that encapsulates all functionality

### Data Models
- `ProfileStatus`: Enum for profile status classifications
- `ProfileProgressData`: Comprehensive profile progress information
- `PhaseOverviewData`: Phase-specific progress data for the overview table

### Widgets
- `ProfileProgressStatusWidget`: Main status display widget
- `PhaseOverviewWidget`: Phase overview table widget

## Usage

### Basic Usage

```python
from aiperf.ui.textual.rich_profile_progress_container import RichProfileProgressContainer
from aiperf.progress.progress_tracker import ProgressTracker

# Create progress tracker
progress_tracker = ProgressTracker()

# Create the container
container = RichProfileProgressContainer(progress_tracker=progress_tracker)

# Add to your Textual app
class MyApp(App):
    def compose(self) -> ComposeResult:
        yield container
```

### Without Phase Overview

```python
container = RichProfileProgressContainer(
    progress_tracker=progress_tracker,
    show_phase_overview=False
)
```

### Updating Progress Data

```python
# Update with new progress tracker
container.update_progress(new_progress_tracker)

# Set progress tracker
container.set_progress_tracker(progress_tracker)

# Update with current tracker
container.update_progress()
```

### Getting Status Information

```python
# Get current profile status
status = container.get_current_status()
print(f"Status: {status}")  # idle, processing, or complete

# Toggle phase overview
container.toggle_phase_overview()
```

## Profile Status Classification

The container classifies profiles into three categories:

1. **Idle**: No profile run is active or profile hasn't started
2. **Processing**: Profile run is actively running with phases in progress
3. **Complete**: All phases have been completed successfully

## Status Display Information

The status widget displays the following information:

- **Status**: Current profile status (Idle/Processing/Complete)
- **Active Phase**: Currently running phase (warmup, steady state, cooldown)
- **Requests**: Request completion statistics with percentage
- **Request Rate**: Current request processing rate (req/s)
- **Request ETA**: Estimated time to complete requests
- **Processed**: Number of processed records
- **Errors**: Error count and percentage with color coding
- **Processing Rate**: Current record processing rate (rec/s)
- **Processing ETA**: Estimated time to complete processing
- **Workers**: Active worker count and total workers
- **Phase Duration**: Duration of the current phase

## Phase Overview Table

The optional phase overview table shows:

- **Phase**: Phase name (warmup, steady state, cooldown)
- **Status**: Phase status (Complete/Running/Pending/Not Started)
- **Progress**: Completion statistics with percentage
- **Rate**: Request processing rate for the phase

## Error Color Coding

Errors are color-coded based on percentage:

- **Green**: 0% errors
- **Yellow**: 1-10% errors
- **Red**: >10% errors

## Data Processing

The container processes data from the `ProgressTracker` and handles:

- **Phase Statistics**: Request counts, completion percentages, timing
- **Computed Statistics**: Rates, ETAs, and derived metrics
- **Processing Statistics**: Record processing and error tracking
- **Worker Statistics**: Active worker counts and task distribution
- **Phase Timing**: Duration calculations and elapsed time

## Example

See `examples/rich_profile_progress_container_example.py` for a complete working example that demonstrates:

- Creating sample profile run data
- Real-time progress updates
- Phase transitions
- Interactive controls for simulation
- Error scenarios and completion

## Integration with Existing Systems

The container is designed to integrate seamlessly with the existing AIPerf Textual UI system. It can be used as a drop-in replacement for the Rich profile progress dashboard while maintaining all functionality.

## Testing

Comprehensive tests are available in `tests/ui/textual/test_rich_profile_progress_container.py` covering:

- Component initialization
- Data processing logic
- Status determination
- Phase overview functionality
- Widget behavior
- Integration testing

## Key Benefits

1. **Consistency**: Provides the same functionality as the Rich version
2. **Modern UI**: Built with Textual for better interactivity
3. **Type Safety**: Uses Pydantic models for robust data handling
4. **Flexibility**: Configurable display options (phase overview toggle)
5. **Performance**: Efficient updates and rendering
6. **Maintainability**: Clean, well-structured code following best practices
7. **Real-time Updates**: Live progress monitoring with automatic refresh

## API Reference

### RichProfileProgressContainer

```python
class RichProfileProgressContainer(Container):
    def __init__(
        self,
        progress_tracker: ProgressTracker | None = None,
        show_phase_overview: bool = True,
    )

    def update_progress(self, progress_tracker: ProgressTracker | None = None) -> None
    def set_progress_tracker(self, progress_tracker: ProgressTracker) -> None
    def toggle_phase_overview(self) -> None
    def get_current_status(self) -> ProfileStatus
```

### ProfileStatus

```python
class ProfileStatus(str, Enum):
    COMPLETE = "complete"
    PROCESSING = "processing"
    IDLE = "idle"
```

### ProfileProgressData

Pydantic model containing comprehensive profile progress information including request statistics, processing metrics, worker counts, and phase timing.
