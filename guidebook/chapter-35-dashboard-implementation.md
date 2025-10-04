<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 35: Dashboard Implementation

## Overview

The AIPerf Dashboard is a rich terminal user interface built on the Textual framework. It provides real-time visualization of benchmark progress, metrics, worker status, and logs in an interactive, keyboard-driven interface. This chapter explores the complete dashboard implementation, from the Textual app structure to individual widget components.

## Table of Contents

1. [Textual Framework](#textual-framework)
2. [AIPerfTextualApp](#aiperf

textual-app)
3. [Widget Architecture](#widget-architecture)
4. [Progress Dashboard](#progress-dashboard)
5. [Real-time Metrics Dashboard](#realtime-metrics-dashboard)
6. [Worker Dashboard](#worker-dashboard)
7. [Log Viewer](#log-viewer)
8. [Layout and Styling](#layout-and-styling)
9. [Keyboard Bindings](#keyboard-bindings)
10. [Theme System](#theme-system)

## Textual Framework

### Framework Overview

Textual is a Python framework for building sophisticated terminal user interfaces:

```python
from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer
from textual.containers import Container

class MyApp(App):
    """A simple Textual app."""

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield Container(Static("Hello, Textual!"))
        yield Footer()
```

**Key Features**:
- Reactive widgets that update automatically
- CSS-like styling system
- Rich text rendering
- Keyboard and mouse event handling
- Layout containers (Vertical, Horizontal, Grid)

### Textual in AIPerf

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/ui/dashboard/aiperf_textual_app.py`:

```python
from textual.app import App

class AIPerfTextualApp(App):
    """AIPerf Textual App."""

    ENABLE_COMMAND_PALETTE = False
    ALLOW_IN_MAXIMIZED_VIEW = "ProgressHeader, Footer"
    NOTIFICATION_TIMEOUT = 3

    def __init__(self, service_config: ServiceConfig, controller: SystemController):
        super().__init__()
        self.title = "NVIDIA AIPerf"
        self.service_config = service_config
        self.controller = controller
```

## AIPerfTextualApp

### App Structure

The main application class orchestrates all components:

```python
class AIPerfTextualApp(App):
    """Main AIPerf dashboard application."""

    # CSS styling
    CSS = """
    #main-container {
        height: 100%;
    }
    #dashboard-section {
        height: 3fr;
        min-height: 14;
    }
    #logs-section {
        height: 2fr;
        max-height: 16;
    }
    #workers-section {
        height: 3;
    }
    """

    # Keyboard bindings
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("1", "minimize_all_panels", "Overview"),
        ("2", "toggle_maximize('progress')", "Progress"),
        ("3", "toggle_maximize('metrics')", "Metrics"),
        ("4", "toggle_maximize('workers')", "Workers"),
        ("5", "toggle_maximize('logs')", "Logs"),
        ("escape", "restore_all_panels", "Restore View"),
    ]
```

### Layout Composition

The `compose` method defines the widget hierarchy:

```python
def compose(self) -> ComposeResult:
    """Compose the full application layout."""
    self.progress_header = ProgressHeader(title=self.title, id="progress-header")
    yield self.progress_header

    with Vertical(id="main-container"):
        with Container(id="dashboard-section"):
            with Horizontal(id="overview-section"):
                with Container(id="progress-section"):
                    self.progress_dashboard = ProgressDashboard(id="progress")
                    yield self.progress_dashboard

                with Container(id="metrics-section"):
                    self.realtime_metrics_dashboard = RealtimeMetricsDashboard(
                        service_config=self.service_config, id="metrics"
                    )
                    yield self.realtime_metrics_dashboard

        with Container(id="workers-section", classes="hidden"):
            self.worker_dashboard = WorkerDashboard(id="workers")
            yield self.worker_dashboard

        with Container(id="logs-section"):
            self.log_viewer = RichLogViewer(id="logs")
            yield self.log_viewer

    yield Footer()
```

### Event Handlers

Dashboard responds to AIPerf events:

```python
async def on_warmup_progress(self, warmup_stats: RequestsStats) -> None:
    """Handle warmup progress updates."""
    if not self._warmup_stats:
        self.query_one("#progress-section").remove_class("hidden")
    self._warmup_stats = warmup_stats

    if self.progress_dashboard:
        async with self.progress_dashboard.batch():
            self.progress_dashboard.on_warmup_progress(warmup_stats)

    if self.progress_header:
        self.progress_header.update_progress(
            header="Warmup",
            progress=warmup_stats.finished,
            total=warmup_stats.total_expected_requests,
        )
```

## Widget Architecture

### Custom Widget Base

All dashboard widgets extend Textual's `Static` widget:

```python
from textual.widgets import Static
from rich.console import RenderableType

class DashboardWidget(Static):
    """Base class for dashboard widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Widget Title"

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self.border = "rounded"
        self.border_title = self.border_title

    def render(self) -> RenderableType:
        """Render the widget content."""
        return "[yellow]Override this method[/yellow]"
```

### Reactive Properties

Textual's reactive system automatically updates the UI:

```python
from textual.reactive import reactive

class MetricWidget(Static):
    """Widget with reactive properties."""

    value = reactive(0.0)
    status = reactive("idle")

    def watch_value(self, old_value: float, new_value: float) -> None:
        """Called when value changes."""
        self.refresh()  # Trigger re-render

    def render(self) -> RenderableType:
        """Render current value."""
        return f"Value: {self.value:.2f} | Status: {self.status}"
```

### Batch Updates

Use batching for multiple updates:

```python
async def update_metrics(self, metrics: list[MetricResult]):
    """Update multiple metrics efficiently."""
    async with self.batch():
        for metric in metrics:
            self.update_metric(metric.tag, metric.avg)
```

## Progress Dashboard

### Progress Display

Shows benchmark phases and progress:

```python
class ProgressDashboard(Static):
    """Dashboard for benchmark progress."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Progress"
        self._warmup_stats: RequestsStats | None = None
        self._profiling_stats: RequestsStats | None = None

    def on_warmup_progress(self, stats: RequestsStats) -> None:
        """Update warmup progress."""
        self._warmup_stats = stats
        self.refresh()

    def on_profiling_progress(self, stats: RequestsStats) -> None:
        """Update profiling progress."""
        self._profiling_stats = stats
        self.refresh()

    def render(self) -> RenderableType:
        """Render progress information."""
        table = Table.grid(padding=(0, 2))
        table.add_column("Phase", style="cyan")
        table.add_column("Progress", style="green")

        if self._warmup_stats:
            table.add_row(
                "Warmup",
                f"{self._warmup_stats.finished}/{self._warmup_stats.total}"
            )

        if self._profiling_stats:
            table.add_row(
                "Profiling",
                f"{self._profiling_stats.finished}/{self._profiling_stats.total}"
            )

        return table
```

## Real-time Metrics Dashboard

### Metrics Display

Displays live performance metrics:

```python
class RealtimeMetricsDashboard(Static):
    """Dashboard for real-time metrics."""

    def __init__(self, service_config: ServiceConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Metrics"
        self.metrics: dict[str, MetricResult] = {}

    def on_realtime_metrics(self, metrics: list[MetricResult]) -> None:
        """Update metrics display."""
        for metric in metrics:
            self.metrics[metric.tag] = metric
        self.refresh()

    def render(self) -> RenderableType:
        """Render metrics table."""
        table = Table()
        table.add_column("Metric", style="cyan")
        table.add_column("Current", justify="right", style="green")
        table.add_column("Average", justify="right", style="yellow")

        for tag, metric in sorted(self.metrics.items()):
            table.add_row(
                metric.header,
                f"{metric.latest:.2f}",
                f"{metric.avg:.2f}"
            )

        return table if self.metrics else "[dim]No metrics yet[/dim]"
```

## Worker Dashboard

### Worker Status Display

Shows status of all workers:

```python
class WorkerDashboard(Static):
    """Dashboard for worker status."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Workers"
        self.workers: dict[str, WorkerStats] = {}

    def on_worker_update(self, worker_id: str, worker_stats: WorkerStats) -> None:
        """Update worker status."""
        self.workers[worker_id] = worker_stats
        self.refresh()

    def render(self) -> RenderableType:
        """Render worker status table."""
        table = Table()
        table.add_column("Worker", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Requests", justify="right")

        for worker_id, stats in sorted(self.workers.items()):
            status_color = {
                WorkerStatus.RUNNING: "green",
                WorkerStatus.IDLE: "yellow",
                WorkerStatus.ERROR: "red",
            }.get(stats.status, "white")

            table.add_row(
                worker_id,
                f"[{status_color}]{stats.status.value}[/{status_color}]",
                str(stats.requests_completed)
            )

        return table if self.workers else "[dim]No workers[/dim]"
```

## Log Viewer

### Rich Log Display

Displays formatted log messages:

```python
from textual.widgets import RichLog

class RichLogViewer(RichLog):
    """Log viewer widget with filtering."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Logs"
        self.max_lines = 1000

    def add_log(self, log_data: dict) -> None:
        """Add a log entry."""
        timestamp = datetime.fromtimestamp(log_data["created"])
        level = log_data["levelname"]
        message = log_data["msg"]
        service = log_data.get("service_id", "unknown")

        # Color by log level
        level_colors = {
            "DEBUG": "blue",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bright_red",
        }
        color = level_colors.get(level, "white")

        # Format log line
        log_line = (
            f"[dim]{timestamp:%H:%M:%S}[/dim] "
            f"[{color}]{level:8s}[/{color}] "
            f"[cyan]{service}[/cyan] "
            f"{message}"
        )

        self.write(log_line)
```

## Layout and Styling

### CSS Styling

Textual uses CSS-like syntax:

```python
CSS = """
/* Main container */
#main-container {
    height: 100%;
    layout: vertical;
}

/* Dashboard section */
#dashboard-section {
    height: 3fr;
    min-height: 14;
    layout: horizontal;
}

/* Progress section */
#progress-section {
    width: 1fr;
    border: solid green;
}

/* Metrics section */
#metrics-section {
    width: 2fr;
    border: solid blue;
}

/* Log viewer */
#logs-section {
    height: 2fr;
    max-height: 16;
    border: solid yellow;
}

/* Hidden class */
.hidden {
    display: none;
}
"""
```

### Container Layout

Containers organize widgets:

```python
# Vertical layout
with Vertical():
    yield Widget1()
    yield Widget2()

# Horizontal layout
with Horizontal():
    yield Widget3()
    yield Widget4()

# Grid layout
with Grid():
    yield Widget5()
    yield Widget6()
```

## Keyboard Bindings

### Action Bindings

Map keys to actions:

```python
BINDINGS = [
    # Quit application
    ("ctrl+c", "quit", "Quit"),

    # View switching
    ("1", "minimize_all_panels", "Overview"),
    ("2", "toggle_maximize('progress')", "Progress"),
    ("3", "toggle_maximize('metrics')", "Metrics"),
    ("4", "toggle_maximize('workers')", "Workers"),
    ("5", "toggle_maximize('logs')", "Logs"),

    # View restoration
    ("escape", "restore_all_panels", "Restore View"),

    # Hidden bindings
    Binding("ctrl+s", "screenshot", "Save Screenshot", show=False),
    Binding("l", "toggle_hide_log_viewer", "Toggle Logs", show=False),
]
```

### Action Handlers

Implement action methods:

```python
async def action_quit(self) -> None:
    """Handle quit action."""
    self.exit(return_code=0)
    # Cleanup
    self.worker_dashboard = None
    self.progress_dashboard = None
    # Forward signal to main process
    os.kill(os.getpid(), signal.SIGINT)

async def action_toggle_maximize(self, panel_id: str) -> None:
    """Toggle panel maximize state."""
    panel = self.query_one(f"#{panel_id}")
    if panel and panel.is_maximized:
        self.screen.minimize()
    else:
        self.screen.maximize(panel)

async def action_restore_all_panels(self) -> None:
    """Restore all panels to default view."""
    self.screen.minimize()
    with suppress(Exception):
        self.query_one("#logs-section").remove_class("hidden")
```

## Theme System

### AIPerf Theme

Custom theme definition:

```python
from textual.theme import Theme

AIPERF_THEME = Theme(
    name="aiperf",
    primary="#00ff00",
    secondary="#0080ff",
    warning="#ffff00",
    error="#ff0000",
    success="#00ff00",
    accent="#ff00ff",
    background="#000000",
    surface="#1a1a1a",
    panel="#2a2a2a",
)
```

### Theme Registration

Register and activate theme:

```python
def on_mount(self) -> None:
    """Register theme on mount."""
    self.register_theme(AIPERF_THEME)
    self.theme = AIPERF_THEME.name
```

## Key Takeaways

1. **Textual Framework**: Modern TUI framework with reactive widgets
2. **Modular Widgets**: Dashboard composed of independent, reusable widgets
3. **Real-time Updates**: Automatic UI updates via reactive properties
4. **Rich Integration**: Full Rich library support for formatting
5. **Keyboard-Driven**: Comprehensive keyboard shortcuts for navigation
6. **CSS Styling**: Familiar CSS-like styling system
7. **Layout Flexibility**: Vertical, horizontal, and grid layouts
8. **Log Integration**: Built-in log viewer with filtering
9. **Theme Support**: Customizable color themes
10. **Batch Updates**: Efficient batch rendering for multiple changes
11. **Responsive Design**: Adapts to terminal size
12. **Interactive**: Mouse and keyboard event handling

## Navigation

- Previous: [Chapter 34: UI Architecture](chapter-34-ui-architecture.md)
- Next: [Chapter 36: Exporters System](chapter-36-exporters-system.md)
- [Back to Index](INDEX.md)
