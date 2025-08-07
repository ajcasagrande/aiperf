# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
ZMQ Warning Suppressor to filter out harmless shutdown warnings.

The "Future <Future cancelled> completed while awaiting" warnings are normal
during shutdown and don't indicate any actual problems. This module provides
a way to suppress these warnings while keeping other important warnings.
"""

import re
import warnings
from typing import Any


class ZMQShutdownWarningFilter:
    """Filter to suppress harmless ZMQ shutdown warnings."""

    def __init__(self):
        self.zmq_shutdown_pattern = re.compile(
            r"Future.*cancelled.*completed while awaiting.*A message has been dropped"
        )

    def __call__(
        self,
        message: str,
        category: type,
        filename: str,
        lineno: int,
        file: Any = None,
        line: str = None,
    ):
        """Filter function for warnings.showwarning"""
        # Suppress ZMQ shutdown warnings
        if (
            category == RuntimeWarning
            and "zmq" in filename.lower()
            and (
                "Future" in str(message)
                and "cancelled" in str(message)
                and "completed while awaiting" in str(message)
            )
        ):
            return  # Suppress this warning

        # Show all other warnings normally
        return self.original_showwarning(
            message, category, filename, lineno, file, line
        )


def suppress_zmq_shutdown_warnings():
    """
    Suppress harmless ZMQ shutdown warnings while keeping other warnings.

    Call this function during application startup to filter out the noise
    from ZMQ future cancellation during shutdown.
    """
    warning_filter = ZMQShutdownWarningFilter()

    # Store original showwarning function
    warning_filter.original_showwarning = warnings.showwarning

    # Replace with our filter
    warnings.showwarning = warning_filter

    # Also add a filter for the specific runtime warning
    warnings.filterwarnings(
        "ignore",
        message=".*Future.*cancelled.*completed while awaiting.*",
        category=RuntimeWarning,
        module="zmq.*",
    )

    print("ZMQ shutdown warning suppression enabled")


def restore_warnings():
    """Restore original warning behavior."""
    # This would need to store and restore the original state
    # For now, just reset to default
    warnings.resetwarnings()
    print("Warning suppression disabled")


# Context manager for temporary warning suppression
class SuppressZMQWarnings:
    """Context manager to temporarily suppress ZMQ warnings."""

    def __enter__(self):
        suppress_zmq_shutdown_warnings()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        restore_warnings()
        return False
