# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from tqdm import tqdm

from aiperf.progress.progress_tracker import ProgressTracker


class SimpleProgressLogger:
    """Simple logger for progress updates. It will use tqdm to show a progress bar."""

    def __init__(self, progress_tracker: ProgressTracker):
        self.logger = logging.getLogger(__name__)
        self.progress_tracker = progress_tracker
        self.tqdm_requests: tqdm | None = None
        self.tqdm_records: tqdm | None = None

    async def update_progress(self):
        """Log a progress update."""
        cur_profile = self.progress_tracker.current_profile
        if cur_profile is None:
            return

        # self.logger.info(
        #     "Requests Completed: %d / %d",
        #     cur_profile.requests_completed,
        #     cur_profile.total_expected_requests,
        # )

        if self.tqdm_requests is None:
            self.tqdm_requests = tqdm(
                total=cur_profile.total_expected_requests,
                desc="Requests Completed",
                colour="green",
            )
        if self.tqdm_requests is not None:
            self.tqdm_requests.n = cur_profile.requests_completed
            self.tqdm_requests.refresh()

        if (
            cur_profile.requests_completed == cur_profile.total_expected_requests
            and self.tqdm_requests is not None
        ):
            self.tqdm_requests.close()
            self.tqdm_requests = None

    async def update_stats(self):
        """Log a stats update."""
        cur_profile = self.progress_tracker.current_profile
        if cur_profile is None:
            return

        # self.logger.info(
        #     "Records Processed: %d / %d",
        #     cur_profile.requests_processed,
        #     cur_profile.total_expected_requests,
        # )

        if self.tqdm_records is None:
            self.tqdm_records = tqdm(
                total=cur_profile.total_expected_requests,
                desc=" Records Processed",
                colour="blue",
            )
        if self.tqdm_records is not None:
            self.tqdm_records.n = cur_profile.requests_processed
            self.tqdm_records.refresh()

        if (
            cur_profile.requests_processed == cur_profile.total_expected_requests
            and self.tqdm_records is not None
        ):
            self.logger.info(
                "Closing TQDM. Records Processed: %d / %d",
                cur_profile.requests_processed,
                cur_profile.total_expected_requests,
            )
            self.tqdm_records.close()
            self.tqdm_records = None

    async def update_results(self):
        """Log a results update."""
        if self.tqdm_requests is not None:
            self.tqdm_requests.close()
            self.tqdm_requests = None

        if self.tqdm_records is not None:
            self.tqdm_records.close()
            self.tqdm_records = None
