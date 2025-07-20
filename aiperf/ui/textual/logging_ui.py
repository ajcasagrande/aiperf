# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import RichLog


class LogViewer(Container):
    DEFAULT_CSS = """
    #log-content {
        border: round $primary;
        border-title-color: $primary;
        height: 100%;
        padding: 0;
        margin: 0;
        scrollbar-gutter: stable;
        &:focus {
            background-tint: $foreground 0%;
        }
    }
    """

    MAX_LOG_LINES = 1000

    border_title = "System Logs"

    LOG_LEVEL_STYLES = {
        "TRACE": "dim",
        "DEBUG": "dim",
        "INFO": "green",
        "NOTICE": "blue",
        "WARNING": "yellow",
        "SUCCESS": "bold green",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log_widget: RichLog | None = None

    def compose(self) -> ComposeResult:
        self.log_widget = RichLog(
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True,
            id="log-content",
            max_lines=self.MAX_LOG_LINES,
        )
        yield self.log_widget

    def display_log_record(self, log_data: dict) -> None:
        if not self.log_widget:
            return

        timestamp = datetime.fromtimestamp(log_data["created"]).strftime("%H:%M:%S.%f")[
            :-3
        ]
        level_style = self.LOG_LEVEL_STYLES.get(log_data["levelname"], "white")

        formatted_log = (
            f"[dim]{timestamp}[/dim] "
            f"[blue]{log_data['name']}[/blue] "
            f"[{level_style}]{log_data['levelname']}[/{level_style}] "
            f"{log_data['msg']}"
        )

        self.log_widget.write(formatted_log)
