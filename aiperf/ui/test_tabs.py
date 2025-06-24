# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Simple test script to verify the tabbed interface is working correctly.
"""

import asyncio
import logging
from unittest.mock import Mock

from aiperf.common.models.progress import ProfileProgress
from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.textual_ui import AIPerfTextualApp

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_mock_progress_tracker():
    """Create a mock progress tracker for testing with actual data."""
    mock_tracker = Mock(spec=ProgressTracker)

    # Create mock profile progress with test data
    mock_profile = Mock(spec=ProfileProgress)
    mock_profile.is_complete = False
    mock_profile.was_cancelled = False
    mock_profile.requests_completed = 150
    mock_profile.total_expected_requests = 1000
    mock_profile.request_errors = 5
    mock_profile.requests_processed = 150
    mock_profile.requests_per_second = 25.5
    mock_profile.processed_per_second = 24.8
    mock_profile.elapsed_time = 6.2
    mock_profile.eta = 33.8

    mock_tracker.current_profile = mock_profile
    return mock_tracker


async def test_tabs():
    """Test the tabbed interface."""
    try:
        # Create mock progress tracker with data
        progress_tracker = create_mock_progress_tracker()

        # Create the app
        app = AIPerfTextualApp(progress_tracker)

        logger.info("Testing tabbed interface with mock data...")
        logger.info("Press '1' to switch to Performance tab")
        logger.info("Press '2' to switch to Worker Status tab")
        logger.info("Press 'q' to quit")

        # Run the app
        await app.run_async()

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error running test: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tabs())
