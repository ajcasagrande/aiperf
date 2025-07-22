#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Test app to demonstrate text selection in LogViewer."""

import time

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header

from aiperf.ui.textual.logging_ui import LogViewer


class TestLogApp(App):
    """Test application for LogViewer text selection."""

    CSS = """
    Container {
        height: 100%;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("l", "add_log", "Add Log Entry"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            self.log_viewer = LogViewer()
            yield self.log_viewer
        yield Footer()

    def on_mount(self) -> None:
        """Add some sample log entries when the app starts."""
        sample_logs = [
            {
                "created": time.time(),
                "name": "test.app",
                "levelname": "INFO",
                "msg": "Application started successfully",
            },
            {
                "created": time.time(),
                "name": "test.db",
                "levelname": "DEBUG",
                "msg": "Database connection established",
            },
            {
                "created": time.time(),
                "name": "test.api",
                "levelname": "WARNING",
                "msg": "API rate limit approaching",
            },
            {
                "created": time.time(),
                "name": "test.worker",
                "levelname": "ERROR",
                "msg": "Worker process failed to start",
            },
            {
                "created": time.time(),
                "name": "test.cache",
                "levelname": "SUCCESS",
                "msg": "Cache cleared successfully",
            },
            {
                "created": time.time(),
                "name": "test.auth",
                "levelname": "CRITICAL",
                "msg": "Authentication system failure",
            },
        ]

        for log_data in sample_logs:
            self.log_viewer.display_log_record(log_data)

        # Show instructions
        self.log_viewer.write("\n[bold cyan]Text Selection Instructions:[/bold cyan]")
        self.log_viewer.write(
            "• Click and drag to select text, then press Ctrl+C to copy"
        )
        self.log_viewer.write(
            "• If that doesn't work, try holding SHIFT while selecting (depends on terminal)"
        )
        self.log_viewer.write("• Press Ctrl+C to copy ALL logs to clipboard")
        self.log_viewer.write("• Press 'l' to add more log entries")

    def action_add_log(self) -> None:
        """Add a new log entry."""
        import random

        levels = ["INFO", "DEBUG", "WARNING", "ERROR", "SUCCESS"]
        names = ["app", "db", "api", "worker", "cache", "auth"]
        messages = [
            "Process completed successfully",
            "Connection timeout occurred",
            "Memory usage is high",
            "Task queued for processing",
            "Configuration updated",
            "Service restarted",
        ]

        log_data = {
            "created": time.time(),
            "name": f"test.{random.choice(names)}",
            "levelname": random.choice(levels),
            "msg": random.choice(messages),
        }

        self.log_viewer.display_log_record(log_data)


if __name__ == "__main__":
    app = TestLogApp()
    app.run()
