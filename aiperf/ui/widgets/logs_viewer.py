# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Checkbox, DataTable, Input, Label

from aiperf.ui.base_widgets import InteractiveAIPerfWidget

if TYPE_CHECKING:
    from aiperf.progress.progress_tracker import ProgressTracker


class LogEntry:
    """Represents a single log entry."""

    def __init__(self, timestamp: float, level: str, logger: str, message: str) -> None:
        self.timestamp = timestamp
        self.level = level
        self.logger = logger
        self.message = message
        self.datetime = datetime.fromtimestamp(timestamp)

    def matches_filter(
        self, level_filter: set[str], logger_filter: str, message_filter: str
    ) -> bool:
        """Check if this log entry matches the given filters."""
        if level_filter and self.level not in level_filter:
            return False

        if logger_filter and logger_filter.lower() not in self.logger.lower():
            return False

        if message_filter and message_filter.lower() not in self.message.lower():
            return False

        return True

    def to_table_row(self) -> tuple[str, str, str, str]:
        """Convert to a table row format."""
        timestamp_str = self.datetime.strftime("%H:%M:%S")
        return (timestamp_str, self.level, self.logger[:20], self.message[:80])


class LogsViewerWidget(InteractiveAIPerfWidget):
    """Clean logs viewer widget with simple filtering."""

    DEFAULT_CSS = """
    LogsViewerWidget {
        border: solid #76b900;
        background: #1a1a1a;
        height: 100%;
    }

    LogsViewerWidget .header {
        background: #76b900;
        color: #000000;
        text-style: bold;
        padding: 0 1;
        dock: top;
        height: 3;
    }

    LogsViewerWidget .filters {
        background: #333333;
        border: solid #444444;
        padding: 1;
        margin: 1;
        height: 3;
    }

    LogsViewerWidget .filter-row {
        layout: grid;
        grid-size: 3 1;
        grid-gutter: 1;
        height: 1;
    }

    LogsViewerWidget .logs-table {
        height: 100%;
        padding: 1;
    }

    LogsViewerWidget .controls {
        dock: bottom;
        height: 2;
        padding: 1;
    }

    LogsViewerWidget .status-bar {
        color: #888888;
        padding: 0 1;
    }

    LogsViewerWidget .log-level-ERROR {
        color: #ff0000;
    }

    LogsViewerWidget .log-level-WARNING {
        color: #ffaa00;
    }

    LogsViewerWidget .log-level-INFO {
        color: #00ff00;
    }

    LogsViewerWidget .log-level-DEBUG {
        color: #888888;
    }
    """

    class LogEntrySelected(Message):
        """Message sent when a log entry is selected."""

        def __init__(self, log_entry: LogEntry) -> None:
            super().__init__()
            self.log_entry = log_entry

    widget_title = "System Logs"

    def __init__(
        self, progress_tracker: "ProgressTracker", max_logs: int = 1000, **kwargs
    ) -> None:
        super().__init__(progress_tracker, **kwargs)
        self.max_logs = max_logs
        self.log_entries: deque[LogEntry] = deque(maxlen=max_logs)
        self.filtered_entries: list[LogEntry] = []
        self.level_filter: set[str] = {
            "ERROR",
            "WARNING",
            "INFO",
        }  # Default to show important logs
        self.logger_filter: str = ""
        self.message_filter: str = ""

    def compose(self) -> ComposeResult:
        """Compose the logs viewer widget."""
        with Vertical():
            # Header
            with Vertical(classes="header"):
                yield Label("System Logs", classes="title")
                yield Label("No logs", id="log-count", classes="status-bar")

            # Simple filters
            with Vertical(classes="filters"):
                with Horizontal(classes="filter-row"):
                    yield Checkbox("Errors", id="filter-error", value=True)
                    yield Checkbox("Warnings", id="filter-warning", value=True)
                    yield Checkbox("Info", id="filter-info", value=True)
                with Horizontal(classes="filter-row"):
                    yield Input(placeholder="Filter by logger...", id="logger-filter")
                    yield Input(
                        placeholder="Search in messages...", id="message-filter"
                    )
                    yield Button("Clear Filters", id="clear-filters", variant="outline")

            # Logs table
            with Vertical(classes="logs-table"):
                logs_table = DataTable(id="logs-table")
                logs_table.add_columns("Time", "Level", "Logger", "Message")
                logs_table.cursor_type = "row"
                yield logs_table

            # Controls
            with Horizontal(classes="controls"):
                yield Button("Clear Logs", id="clear-logs", variant="error")
                yield Button("Export", id="export-logs", variant="outline")
                yield Label("", id="status-info", classes="status-bar")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self._update_status()

    def update_content(self) -> None:
        """Update the logs display."""
        self._apply_filters()
        self._update_table()
        self._update_status()

    def add_log_entry(
        self, timestamp: float, level: str, logger: str, message: str
    ) -> None:
        """Add a new log entry."""
        entry = LogEntry(timestamp, level, logger, message)
        self.log_entries.append(entry)

        # Update display if entry matches current filters
        if entry.matches_filter(
            self.level_filter, self.logger_filter, self.message_filter
        ):
            self.filtered_entries.append(entry)
            self._update_table()
            self._update_status()

    def _apply_filters(self) -> None:
        """Apply current filters to log entries."""
        self.filtered_entries = []
        for entry in self.log_entries:
            if entry.matches_filter(
                self.level_filter, self.logger_filter, self.message_filter
            ):
                self.filtered_entries.append(entry)

    def _update_table(self) -> None:
        """Update the logs table with filtered entries."""
        table = self.query_one("#logs-table", DataTable)
        table.clear()

        for entry in self.filtered_entries[-100:]:  # Show last 100 entries
            table.add_row(*entry.to_table_row(), classes=f"log-level-{entry.level}")

    def _update_status(self) -> None:
        """Update the status information."""
        log_count = self.query_one("#log-count", Label)
        log_count.update(
            f"{len(self.log_entries)} total logs, {len(self.filtered_entries)} filtered"
        )

        status_info = self.query_one("#status-info", Label)
        if self.filtered_entries:
            latest_entry = self.filtered_entries[-1]
            status_info.update(
                f"Latest: {latest_entry.level} from {latest_entry.logger}"
            )
        else:
            status_info.update("No logs match filters")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle filter checkbox changes."""
        if event.checkbox.id == "filter-error":
            if event.value:
                self.level_filter.add("ERROR")
            else:
                self.level_filter.discard("ERROR")
        elif event.checkbox.id == "filter-warning":
            if event.value:
                self.level_filter.add("WARNING")
            else:
                self.level_filter.discard("WARNING")
        elif event.checkbox.id == "filter-info":
            if event.value:
                self.level_filter.add("INFO")
            else:
                self.level_filter.discard("INFO")

        self.update_content()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "logger-filter":
            self.logger_filter = event.value
        elif event.input.id == "message-filter":
            self.message_filter = event.value

        self.update_content()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "clear-logs":
            self.action_clear_logs()
        elif event.button.id == "export-logs":
            self.action_export_logs()
        elif event.button.id == "clear-filters":
            self.action_clear_filters()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle log entry selection."""
        if event.row_index < len(self.filtered_entries):
            selected_entry = self.filtered_entries[event.row_index]
            self.post_message(self.LogEntrySelected(selected_entry))

    def action_clear_logs(self) -> None:
        """Clear all log entries."""
        self.log_entries.clear()
        self.filtered_entries.clear()
        self._update_table()
        self._update_status()
        self.notify("Logs cleared")

    def action_export_logs(self) -> None:
        """Export logs (placeholder)."""
        self.notify("Export functionality not implemented yet")

    def action_clear_filters(self) -> None:
        """Clear all filters."""
        self.level_filter = {"ERROR", "WARNING", "INFO"}
        self.logger_filter = ""
        self.message_filter = ""

        # Reset UI elements
        self.query_one("#filter-error", Checkbox).value = True
        self.query_one("#filter-warning", Checkbox).value = True
        self.query_one("#filter-info", Checkbox).value = True
        self.query_one("#logger-filter", Input).value = ""
        self.query_one("#message-filter", Input).value = ""

        self.update_content()
        self.notify("Filters cleared")

    def get_log_summary(self) -> dict:
        """Get a summary of log statistics."""
        if not self.log_entries:
            return {}

        level_counts = {}
        for entry in self.log_entries:
            level_counts[entry.level] = level_counts.get(entry.level, 0) + 1

        return {
            "total_logs": len(self.log_entries),
            "filtered_logs": len(self.filtered_entries),
            "level_counts": level_counts,
            "oldest_log": self.log_entries[0].datetime if self.log_entries else None,
            "newest_log": self.log_entries[-1].datetime if self.log_entries else None,
        }

    def get_recent_errors(self, count: int = 10) -> list[LogEntry]:
        """Get the most recent error log entries."""
        errors = [entry for entry in self.log_entries if entry.level == "ERROR"]
        return errors[-count:] if errors else []
