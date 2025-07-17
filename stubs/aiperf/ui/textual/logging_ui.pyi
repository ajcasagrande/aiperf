#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging

from _typeshed import Incomplete
from textual.app import ComposeResult as ComposeResult
from textual.containers import Container
from textual.widgets import RichLog

class TextualLogHandler(logging.Handler):
    DEFAULT_CSS: str
    LOG_LEVEL_STYLES: Incomplete
    log_widget: Incomplete
    def __init__(self, log_widget: RichLog) -> None: ...
    def emit(self, record: logging.LogRecord) -> None: ...

class LogViewer(Container):
    DEFAULT_CSS: str
    border_title: str
    log_widget: RichLog | None
    log_handler: TextualLogHandler | None
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def on_mount(self) -> None: ...
    def on_unmount(self) -> None: ...
