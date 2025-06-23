#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

"""
Simple test script to verify the tabbed interface is working correctly.
"""

import asyncio
import logging
from unittest.mock import Mock

from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.textual_ui import AIPerfTextualApp

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_mock_progress_tracker():
    """Create a mock progress tracker for testing."""
    mock_tracker = Mock(spec=ProgressTracker)
    mock_tracker.current_profile = None
    return mock_tracker


async def test_tabs():
    """Test the tabbed interface."""
    try:
        # Create mock progress tracker
        progress_tracker = create_mock_progress_tracker()

        # Create the app
        app = AIPerfTextualApp(progress_tracker)

        logger.info("Testing tabbed interface...")
        logger.info("Press '1' to switch to Performance tab")
        logger.info("Press '2' to switch to Worker Status tab")
        logger.info("Press 'q' to quit")

        # Run the app
        await app.run_async()

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error running test: {e}")


if __name__ == "__main__":
    asyncio.run(test_tabs())
