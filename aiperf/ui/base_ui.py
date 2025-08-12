# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.mixins import (
    MetricsPreviewMixin,
    ProgressTrackerMixin,
    WorkerTrackerMixin,
)


class BaseAIPerfUI(ProgressTrackerMixin, WorkerTrackerMixin, MetricsPreviewMixin):
    """Base class for AIPerf UI implementations.

    This class provides a simple starting point for a UI for AIPerf components.
    It inherits from the :class:`ProgressTrackerMixin`, :class:`WorkerTrackerMixin`, and :class:`MetricsPreviewMixin`
    to provide a simple starting point for a UI for AIPerf components.

    Now, you can use the various hooks defined in the :class:`ProgressTrackerMixin`, :class:`WorkerTrackerMixin`, and :class:`MetricsPreviewMixin`
    to create a UI for AIPerf components.

    Example:
    ```python
    @AIPerfUIFactory.register("custom")
    class MyUI(BaseAIPerfUI):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        @on_records_progress
        def _on_records_progress(self, records_stats: RecordsStats):
            '''Callback for records progress updates.'''
            pass

        @on_warmup_progress
        def _on_warmup_progress(self, requests_stats: RequestsStats):
            '''Callback for warmup progress updates.'''
            pass

        @on_profiling_progress
        def _on_profiling_progress(self, requests_stats: RequestsStats):
            '''Callback for profiling progress updates.'''
            pass

        @on_worker_status_summary
        def _on_worker_status_summary(self, worker_status_summary: dict[str, WorkerStatus]):
            '''Callback for worker status summary updates.'''
            pass

        @on_worker_update
        def _on_worker_update(self, worker_id: str, worker_stats: WorkerStats):
            '''Callback for worker updates.'''
            pass

        @on_metrics_preview
        def _on_metrics_preview(self, metrics_preview: list[MetricResult]):
            '''Callback for metrics preview updates.'''
            pass
    ```
    """
