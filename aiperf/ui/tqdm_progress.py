# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from tqdm import tqdm

from aiperf.common.constants import DEFAULT_UI_MIN_UPDATE_PERCENT
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import AIPerfUIType, CreditPhase
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.hooks import (
    on_records_progress,
    on_requests_phase_progress,
    on_stop,
)
from aiperf.common.models import RecordsStats, RequestsStats
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.ui.base_ui import BaseAIPerfUI


class ProgressBar:
    """A progress bar that can be updated with a progress percentage."""

    def __init__(
        self,
        desc: str,
        colour: str,
        position: int,
        update_threshold: float = DEFAULT_UI_MIN_UPDATE_PERCENT,
        **kwargs,
    ):
        self.bar = tqdm(
            total=100,
            desc=desc,
            colour=colour,
            position=position,
            leave=False,
            dynamic_ncols=False,
            unit=" pct",
            bar_format="{desc}: {percentage:3.0f}% |{bar}| {percentage:3.0f}% [{elapsed}<{remaining}]",
            **kwargs,
        )
        self.update_threshold = update_threshold
        self.last_progress = 0.0

    def update(self, progress: float):
        """Update the progress bar with a new progress percentage."""
        if progress > self.last_progress + self.update_threshold:
            self.bar.update(progress - self.last_progress)
            self.last_progress = progress

    def close(self):
        """Close the progress bar."""
        self.bar.close()


@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register(AIPerfUIType.SIMPLE)
class TQDMProgressUI(BaseAIPerfUI):
    """A UI that shows progress bars for the records and requests phases."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._records_bar: ProgressBar | None = None
        self._requests_bar: ProgressBar | None = None
        self._warmup_bar: ProgressBar | None = None

    @on_stop
    def _close_all_bars(self):
        """Close all progress bars."""
        for bar in [self._records_bar, self._requests_bar, self._warmup_bar]:
            if bar is not None:
                bar.close()

    @on_records_progress
    def _on_records_progress(self, records_stats: RecordsStats):
        """Callback for records progress updates."""
        if self._records_bar is None and records_stats.progress_percent is not None:
            self._records_bar = ProgressBar(
                desc=f" Records ({CreditPhase.PROFILING.capitalize()})",
                colour="blue",
                position=2,  # bottom position
            )

        if self._records_bar:
            self._records_bar.update(records_stats.progress_percent)

    @on_requests_phase_progress
    def _on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ):
        """Callback for requests phase progress updates."""
        if phase == CreditPhase.WARMUP:
            if self._warmup_bar is None and requests_stats.progress_percent is not None:
                self._warmup_bar = ProgressBar(
                    desc="Warmup",
                    colour="yellow",
                    position=0,  # top position
                )

            if self._warmup_bar:
                self._warmup_bar.update(requests_stats.progress_percent)

        elif phase == CreditPhase.PROFILING:
            if (
                self._requests_bar is None
                and requests_stats.progress_percent is not None
            ):
                self._requests_bar = ProgressBar(
                    desc=f"Requests ({phase.capitalize()})",
                    colour="green",
                    position=1,  # second position
                )

            if self._requests_bar:
                self._requests_bar.update(requests_stats.progress_percent)
