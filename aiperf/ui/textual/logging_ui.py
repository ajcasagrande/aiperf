# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from textual.widgets import RichLog


class LogViewer(RichLog):
    DEFAULT_CSS = """
    LogViewer {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        layout: vertical;
        scrollbar-gutter: stable;
        &:focus {
            background-tint: $primary 0%;
        }
    }
    """

    MAX_LOG_LINES = 1000
    MAX_LOG_MESSAGE_LENGTH = 250

    LOG_LEVEL_STYLES = {
        "TRACE": "dim",
        "DEBUG": "dim",
        "INFO": "green",
        "NOTICE": "blue",
        "WARNING": "yellow",
        "SUCCESS": "bold green",
        "Error": "red",
        "CRITICAL": "bold red",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            auto_scroll=True,
            max_lines=self.MAX_LOG_LINES,
            **kwargs,
        )
        self.border_title = "System Logs"

    def display_log_record(self, log_data: dict) -> None:
        timestamp = datetime.fromtimestamp(log_data["created"]).strftime("%H:%M:%S.%f")[
            :-3
        ]
        level_style = self.LOG_LEVEL_STYLES.get(log_data["levelname"], "white")

        formatted_log = (
            f"[dim]{timestamp}[/dim] "
            f"[blue]{log_data['name']}[/blue] "
            f"[{level_style}]{log_data['levelname']}[/{level_style}] "
            f"{log_data['msg'][: self.MAX_LOG_MESSAGE_LENGTH]}"
        )

        self.write(formatted_log)
