# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from tqdm import tqdm

from aiperf.common.enums import AIPerfUIType, CreditPhase
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.hooks import (
    on_records_progress,
    on_requests_phase_progress,
    on_worker_update,
)
from aiperf.common.mixins import AIPerfBaseUIMixin
from aiperf.common.models import (
    RecordsStats,
    RequestsStats,
    WorkerStats,
)


@AIPerfUIFactory.register(AIPerfUIType.TQDM)
class TQDMProgressUI(AIPerfBaseUIMixin):
    """A UI that shows progress bars for the records and requests phases."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._records_bars: tqdm | None = None
        self._requests_bars: tqdm | None = None

    @on_records_progress
    def _on_records_progress(self, records_stats: RecordsStats):
        """Callback for records progress updates."""
        if self._records_bars is None:
            self._records_bars = tqdm(
                total=records_stats.total_expected_requests,
                desc="Records",
                unit="records",
            )
        self._records_bars.update(records_stats.progress_percent)
        self._records_bars.refresh()

    @on_requests_phase_progress
    def _on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ):
        """Callback for requests phase progress updates."""
        if self._requests_bars is None:
            self._requests_bars = tqdm(
                total=requests_stats.total_expected_requests,
                desc=requests_stats.type.value,
                unit="requests",
            )
        self._requests_bars.update(requests_stats.progress_percent)
        self._requests_bars.refresh()

    @on_worker_update
    def _on_worker_update(self, worker_id: str, worker_stats: WorkerStats):
        """Callback for worker updates."""
        pass
