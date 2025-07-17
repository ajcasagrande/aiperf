#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from enum import Enum

from _typeshed import Incomplete
from textual.app import ComposeResult as ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import DataTable

from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.utils import format_duration as format_duration
from aiperf.progress.progress_tracker import ProfileRunProgress as ProfileRunProgress
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker

class ProfileStatus(str, Enum):
    COMPLETE = "complete"
    PROCESSING = "processing"
    IDLE = "idle"

class ProfileProgressData(AIPerfBaseModel):
    profile_id: str | None
    status: ProfileStatus
    active_phase: CreditPhase | None
    requests_completed: int
    requests_total: int | None
    requests_progress_percent: float | None
    requests_per_second: float | None
    requests_eta: str | None
    processed_count: int
    errors_count: int
    error_percent: float
    records_per_second: float | None
    records_eta: str | None
    active_workers: int
    total_workers: int
    phase_duration: str | None
    @property
    def error_color_class(self) -> str: ...

class PhaseOverviewData(AIPerfBaseModel):
    phase: CreditPhase
    status: str
    progress: str
    rate: str
    status_style: str

class ProfileProgressStatusWidget(Widget):
    DEFAULT_CSS: str
    border_title: str
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_progress(self, progress_data: ProfileProgressData) -> None: ...

class PhaseOverviewWidget(Widget):
    DEFAULT_CSS: str
    data_table: DataTable | None
    border_title: str
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_phases(self, phases_data: list[PhaseOverviewData]) -> None: ...

class RichProfileProgressContainer(Container):
    DEFAULT_CSS: str
    progress_tracker: Incomplete
    show_phase_overview: Incomplete
    status_widget: ProfileProgressStatusWidget | None
    phase_widget: PhaseOverviewWidget | None
    border_title: str
    def __init__(
        self,
        progress_tracker: ProgressTracker | None = None,
        show_phase_overview: bool = True,
    ) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_progress(
        self, progress_tracker: ProgressTracker | None = None
    ) -> None: ...
    def on_mount(self) -> None: ...
    def set_progress_tracker(self, progress_tracker: ProgressTracker) -> None: ...
    def toggle_phase_overview(self) -> None: ...
    def get_current_status(self) -> ProfileStatus: ...
