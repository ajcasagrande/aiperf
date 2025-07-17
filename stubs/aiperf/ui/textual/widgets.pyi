#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable
from collections.abc import Generator
from typing import Any

from _typeshed import Incomplete
from rich.text import Text
from textual.events import Mount as Mount
from textual.widget import Widget

from aiperf.progress.progress_tracker import ProfileRunProgress as ProfileRunProgress
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker

logger: Incomplete

class DashboardFormatter:
    @staticmethod
    def format_duration(seconds: float | None) -> str: ...
    @staticmethod
    def format_count_with_total(count: int | None, total: int | None) -> str: ...
    @staticmethod
    def format_percentage(value: float | None) -> str: ...
    @staticmethod
    def format_rate(rate: float | None) -> str: ...
    @staticmethod
    def format_error_stats(
        error_count: int, total: int, error_rate: float | None
    ) -> str: ...

class StatusClassifier:
    @staticmethod
    def get_error_status(error_rate: float | None) -> str: ...
    @staticmethod
    def get_completion_status(is_complete: bool) -> str: ...

class DashboardField:
    field_id: Incomplete
    label: Incomplete
    value_getter: Incomplete
    formatter: Incomplete
    status_classifier: Incomplete
    show_dot: Incomplete
    def __init__(
        self,
        field_id: str,
        label: str,
        value_getter: Callable[[ProgressTracker, ProfileRunProgress], Any],
        formatter: Callable[[Any], str],
        status_classifier: Callable[[Any], str] | None = None,
        show_dot: bool = True,
    ) -> None: ...
    def update(
        self, container: Widget, progress: ProgressTracker, profile: ProfileRunProgress
    ) -> None: ...

class StatusIndicator(Widget):
    DEFAULT_CSS: str
    label: Incomplete
    value: Incomplete
    status_class: Incomplete
    show_dot: Incomplete
    def __init__(
        self,
        label: str,
        value: str = "",
        status_class: str = "",
        show_dot: bool = True,
        **kwargs,
    ) -> None: ...
    def render(self) -> Text: ...
    def update_value(self, value: str, status_class: str = "") -> None: ...

class Header(Widget):
    DEFAULT_CSS: str
    DEFAULT_CLASSES: str
    def __init__(
        self, name: str | None = None, id: str | None = None, classes: str | None = None
    ) -> None: ...
    def compose(self) -> Generator[Incomplete]: ...
    @property
    def screen_title(self) -> str: ...
    @property
    def screen_sub_title(self) -> str: ...
