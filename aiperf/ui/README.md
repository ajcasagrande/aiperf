<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Textual UI System

A comprehensive, interactive terminal-based user interface for the NVIDIA AIPerf system built with the Textual framework.

## Overview

The AIPerf Textual UI provides a modern, interactive dashboard for monitoring and managing AI performance profiling workloads. Built on the Textual framework, it offers:

- **Interactive Widgets**: Click, navigate, and interact with UI elements
- **Real-time Updates**: Live data streaming and automatic refresh
- **Multiple Views**: System overview, phase timeline, worker status, and logs
- **Keyboard Shortcuts**: Efficient navigation and control
- **NVIDIA Styling**: Custom theme matching NVIDIA brand guidelines
- **Export Capabilities**: Data export and configuration management

## Features

### System Overview Widget
- High-level system metrics dashboard
- Real-time performance indicators
- Overall progress tracking
- Executive-level summary information

### Phase Timeline Widget
- Interactive phase progress visualization
- Clickable phase cards with detailed information
- Timeline view of execution phases
- Progress bars and timing information

### Worker Status Widget
- Real-time worker health monitoring
- Individual worker performance metrics
- Interactive worker cards
- Sortable and filterable worker information

### Logs Viewer Widget
- Advanced log filtering and searching
- Real-time log streaming
- Log level filtering and highlighting
- Export and search capabilities

## Installation

The Textual UI is included with AIPerf and requires the `textual` package:

```bash
pip install textual
```

## Usage

### Basic Usage

```python
from aiperf.ui import create_ui
from aiperf.progress.progress_tracker import ProgressTracker

# Create progress tracker
progress_tracker = ProgressTracker()

# Create UI (defaults to Textual)
ui = create_ui(progress_tracker)

# Start the UI
await ui.start()
```

### Advanced Usage

```python
from aiperf.ui import AIPerfAdvancedUI, create_aiperf_ui
from aiperf.progress.progress_tracker import ProgressTracker

# Create progress tracker
progress_tracker = ProgressTracker()

# Create advanced UI with additional features
ui = create_aiperf_ui(progress_tracker, ui_type="advanced")

# Configure custom settings
ui.set_theme("nvidia")
ui.register_keyboard_shortcut("ctrl+r", "refresh_all", "Refresh all widgets")

# Start the UI
await ui.start()
```

### Integration with AIPerf System

The Textual UI integrates seamlessly with the existing AIPerf system:

```python
# In your system controller
from aiperf.ui import AIPerfUI

# Create UI instance
ui = AIPerfUI(progress_tracker)

# Handle progress updates
await ui.on_credit_phase_progress_update(progress_message)
await ui.on_worker_health_update(health_message)

# Add log entries
ui.add_log_entry(timestamp, "INFO", "SystemController", "Profile started")
```

## Keyboard Shortcuts

### Global Shortcuts
- `F1`: Toggle help screen
- `F2`: Toggle theme (dark/light)
- `F5`: Refresh all widgets
- `Ctrl+C` / `Ctrl+Q`: Quit application
- `Tab`: Navigate between widgets
- `Escape`: Close dialogs/screens

### Widget-Specific Shortcuts
- **Phase Timeline**: Click phase cards to view details
- **Worker Status**: Click worker cards for detailed information
- **Logs Viewer**: Use filters and search to find specific logs

## Themes

The UI supports multiple themes:

- **Dark** (default): Standard dark theme
- **Light**: Light theme for bright environments
- **NVIDIA**: Custom NVIDIA-branded theme with green accents

```python
ui.set_theme("nvidia")  # Switch to NVIDIA theme
```

## Widget Architecture

### Base Widget System

All widgets inherit from base classes that provide common functionality:

```python
from aiperf.ui.base_widgets import BaseAIPerfWidget, InteractiveAIPerfWidget

class CustomWidget(InteractiveAIPerfWidget):
    def compose(self) -> ComposeResult:
        # Define widget layout
        pass

    def update_content(self) -> None:
        # Update widget with fresh data
        pass
```

### Widget Registry

Widgets are registered and can be dynamically created:

```python
from aiperf.ui.widgets import create_widget, list_available_widgets

# List available widgets
widgets = list_available_widgets()

# Create widget dynamically
widget = create_widget("system_overview", progress_tracker)
```

## Configuration

### UI Modes

Different UI configurations for different use cases:

```python
# Executive mode - high-level overview
ui = create_ui(progress_tracker, use_case="executive")

# Developer mode - detailed information
ui = create_ui(progress_tracker, use_case="developer")

# Operator mode - operational monitoring
ui = create_ui(progress_tracker, use_case="operator")
```

### Feature Detection

Check available features for different UI types:

```python
from aiperf.ui import get_ui_features

features = get_ui_features("textual")
print(features["interactive"])  # True
print(features["themes"])       # ["dark", "light", "nvidia"]
```

## Extending the UI

### Custom Widgets

Create custom widgets by extending the base classes:

```python
from aiperf.ui.base_widgets import DataDisplayWidget

class CustomMetricsWidget(DataDisplayWidget):
    widget_title = "Custom Metrics"

    def compose(self) -> ComposeResult:
        # Define your widget layout
        yield Label("Custom metrics here")

    def update_content(self) -> None:
        # Update with your data
        pass
```

### Custom Themes

Define custom themes using CSS:

```python
CUSTOM_THEME = """
MyApp.custom-theme {
    $primary: #ff6600;
    $secondary: #0066ff;
    $accent: #ffcc00;
    $success: #00ff00;
    $warning: #ff9900;
    $error: #ff0000;
}
"""
```

## Performance Considerations

### Update Frequency

Widgets update automatically at 1-second intervals. For high-frequency updates:

```python
# Adjust update interval
widget.set_interval(0.5, widget.update_content)  # 500ms updates
```

### Memory Usage

The UI maintains bounded collections for logs and metrics:

```python
# Configure log limits
logs_widget = LogsViewerWidget(progress_tracker, max_logs=5000)
```

## Troubleshooting

### Common Issues

1. **Terminal Size**: Ensure terminal is at least 80x24 characters
2. **Color Support**: Use a terminal with 256-color support
3. **Unicode**: Ensure terminal supports Unicode characters
4. **Keyboard Input**: Some shortcuts may conflict with terminal emulators

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Compatibility

The Textual UI maintains backward compatibility with the Rich UI:

```python
# Legacy Rich UI still works
from aiperf.ui import AIPerfRichDashboard
dashboard = AIPerfRichDashboard(progress_tracker)
```

## API Reference

### Main Classes

- `AIPerfTextualUI`: Main UI class
- `AIPerfAdvancedUI`: Advanced UI with additional features
- `AIPerfTextualDashboard`: Core dashboard implementation
- `SystemOverviewWidget`: System-wide metrics
- `PhaseTimelineWidget`: Phase execution timeline
- `WorkerStatusWidget`: Worker health monitoring
- `LogsViewerWidget`: Log viewing and filtering

### Factory Functions

- `create_ui()`: Create UI instance with automatic type selection
- `create_aiperf_ui()`: Create specific UI type
- `get_recommended_ui()`: Get recommended UI for use case

### Utility Functions

- `get_ui_features()`: Get available features for UI type
- `list_available_widgets()`: List all available widgets
- `create_widget()`: Create widget instance dynamically

## Contributing

To contribute to the UI system:

1. Follow the existing widget patterns
2. Use the base widget classes
3. Include comprehensive CSS styling
4. Add keyboard shortcuts where appropriate
5. Ensure proper error handling
6. Write unit tests for new widgets

## License

Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
Licensed under the Apache-2.0 License.
