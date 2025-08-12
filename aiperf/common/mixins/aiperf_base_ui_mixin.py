# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.mixins.progress_tracker_mixin import ProgressTrackerMixin
from aiperf.common.mixins.worker_tracker_mixin import WorkerTrackerMixin


class AIPerfBaseUIMixin(ProgressTrackerMixin, WorkerTrackerMixin):
    """Mixin to enable a simple starting point for a UI for AIPerf components.

    This mixin provides a simple starting point for a UI for AIPerf components.
    It inherits from the :class:`ProgressTrackerMixin` and :class:`WorkerTrackerMixin`
    to provide a simple starting point for a UI for AIPerf components.

    Now, you can use the various hooks defined in the :class:`ProgressTrackerMixin` and :class:`WorkerTrackerMixin`
    to create a UI for AIPerf components.

    Example:
    ```python
    @AIPerfUIFactory.register("custom")
    class MyUI(AIPerfBaseUIMixin):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        @on_records_progress
        def _on_records_progress(self, records_stats: RecordsStats):
            '''Callback for records progress updates.'''
            pass

        @on_profiling_progress
        def _on_profiling_progress(self, profiling_stats: RequestsStats):
            '''Callback for profiling progress updates.'''
            pass

        @on_warmup_progress
        def _on_warmup_progress(self, warmup_stats: RequestsStats):
            '''Callback for warmup progress updates.'''
            pass

        @on_worker_update
        def _on_worker_update(self, worker_id: str, worker_stats: WorkerStats):
            '''Callback for worker updates.'''
            pass

        @on_worker_status_summary
        def _on_worker_status_summary(self, worker_status_summary: dict[str, WorkerStatus]):
            '''Callback for worker status summary updates.'''
            pass
    ```
    """
