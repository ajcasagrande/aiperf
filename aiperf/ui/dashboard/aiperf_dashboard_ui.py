# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import multiprocessing

from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import AIPerfUIType, CreditPhase
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.hooks import (
    on_records_progress,
    on_requests_phase_progress,
    on_start,
    on_stop,
    on_worker_update,
)
from aiperf.common.models import (
    RecordsStats,
    RequestsStats,
    WorkerStats,
)
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.ui.base_ui import BaseAIPerfUI
from aiperf.ui.dashboard.aiperf_textual_app import AIPerfTextualApp
from aiperf.ui.dashboard.rich_log_viewer import LogConsumer


@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register(AIPerfUIType.DASHBOARD)
class AIPerfDashboardUI(BaseAIPerfUI):
    """
    AIPerf Dashboard UI.

    This is the main UI class for the Dashboard UI. It is responsible for
    managing the Dashboard application, its lifecycle, and passing the
    progress updates to the application.
    """

    def __init__(
        self,
        log_queue: multiprocessing.Queue,
        user_config: UserConfig,
        **kwargs,
    ) -> None:
        super().__init__(user_config=user_config, **kwargs)
        self.user_config = user_config
        self.app: AIPerfTextualApp = AIPerfTextualApp()
        self.log_consumer: LogConsumer = LogConsumer(log_queue=log_queue, app=self.app)
        self.attach_child_lifecycle(self.log_consumer)

    @on_start
    async def _run_app(self) -> None:
        """Run the enhanced Dashboard application."""
        self.debug("Starting AIPerf Dashboard UI...")
        self.execute_async(self.app.run_async())

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the Dashboard application gracefully."""
        if self.app:
            self.debug("Shutting down Dashboard UI")
            self.app.exit(return_code=0)

    @on_records_progress
    async def _on_records_progress(self, records_stats: RecordsStats):
        """Callback for records progress updates."""
        if self.app.overview_progress:
            self.app.overview_progress.on_records_progress(records_stats)
        if self.app.progress_dashboard:
            self.app.progress_dashboard.on_records_progress(records_stats)

    @on_requests_phase_progress
    async def _on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ):
        """Callback for requests phase progress updates."""
        if self.app.overview_progress:
            self.app.overview_progress.on_requests_phase_progress(phase, requests_stats)
        if self.app.progress_dashboard:
            self.app.progress_dashboard.on_requests_phase_progress(
                phase, requests_stats
            )

    @on_worker_update
    async def _on_worker_update(self, worker_id: str, worker_stats: WorkerStats):
        """Callback for worker updates."""
        if self.app.overview_workers:
            self.app.overview_workers.on_worker_stats_update(worker_id, worker_stats)
        if self.app.worker_dashboard:
            self.app.worker_dashboard.on_worker_stats_update(worker_id, worker_stats)
