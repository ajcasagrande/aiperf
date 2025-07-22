# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from rich.cells import cell_len
from rich.highlighter import JSONHighlighter
from rich.style import Style
from rich.text import Text
from textual.strip import Strip
from textual.widgets import Log, RichLog


class RichLogViewer(RichLog):
    DEFAULT_CSS = """
    RichLogViewer {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        layout: vertical;
        width: 100%;
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
        "ERROR": "red",
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


class CustomLog(Log):
    def __init__(self, highlight: bool = True, markup: bool = True, **kwargs) -> None:
        super().__init__(highlight=highlight, **kwargs)
        self.markup = markup
        self.highlight = highlight
        if self.highlight:
            self.highlighter = JSONHighlighter()

    def _render_line_strip(self, y: int, rich_style: Style) -> Strip:
        """Render a line into a Strip.

        Args:
            y: Y offset of line.
            rich_style: Rich style of line.

        Returns:
            An uncropped Strip.
        """
        selection = self.text_selection
        if y in self._render_line_cache and selection is None:
            return self._render_line_cache[y]

        _line = self._process_line(self._lines[y])

        if self.markup:
            line_text = Text.from_markup(_line, style=rich_style, end="")
        else:
            line_text = Text(_line, no_wrap=True)
            line_text.stylize(rich_style)

        if self.highlight:
            line_text = self.highlighter(line_text)
        if (
            selection is not None
            and (select_span := selection.get_span(y - self._clear_y)) is not None
        ):
            start, end = select_span
            if end == -1:
                end = len(line_text)

            selection_style = self.screen.get_component_rich_style("screen--selection")
            line_text.stylize(selection_style, start, end)

        line = Strip(line_text.render(self.app.console), cell_len(_line))

        if selection is not None:
            self._render_line_cache[y] = line
        return line


# class LogViewer(CustomLog):
class LogViewer(RichLog):
    DEFAULT_CSS = """
    LogViewer {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        layout: vertical;
        width: 100%;
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
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(
            highlight=True,
            markup=True,
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
            f"[{level_style}]{log_data['levelname']: >8}[/{level_style}] "
            f"[blue]{log_data['name']}[/blue] "
            f"{log_data['msg'][: self.MAX_LOG_MESSAGE_LENGTH]}"
        )

        self.write(formatted_log)
