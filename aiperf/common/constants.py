# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

NANOS_PER_SECOND = 1_000_000_000
NANOS_PER_MILLIS = 1_000_000
BYTES_PER_MIB = 1024 * 1024

GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 5.0
"""Default timeout for shutting down services in seconds."""

DEFAULT_SHUTDOWN_ACK_TIMEOUT = 5.0
"""Default timeout for waiting for a shutdown command response in seconds."""

DEFAULT_PROFILE_CANCEL_TIMEOUT = 10.0
"""Default timeout for cancelling a profile run in seconds."""

TASK_CANCEL_TIMEOUT_SHORT = 2.0
"""Maximum time to wait for simple tasks to complete when cancelling them."""

TASK_CANCEL_TIMEOUT_LONG = 5.0
"""Maximum time to wait for complex tasks to complete when cancelling them (like parent tasks)."""

# High-performance communication defaults for zero timeout guarantee
DEFAULT_DEALER_SEND_QUEUE_SIZE = (
    1_000_000  # Increased from 500k for zero timeout guarantee
)
DEFAULT_DEALER_RECV_QUEUE_SIZE = (
    1_000_000  # Increased from 500k for zero timeout guarantee
)
DEFAULT_PULL_CLIENT_MAX_CONCURRENCY = (
    1_000_000  # Increased from 500k for zero timeout guarantee
)

# Timeout settings - very high to prevent any timeouts
DEFAULT_COMMS_REQUEST_TIMEOUT = 300.0  # Increased to 5 minutes from 120s
DEFAULT_COMMS_COMMAND_TIMEOUT = 300.0  # Increased to 5 minutes

# New constants for high-performance scenarios
EXTREME_CONCURRENCY_THRESHOLD = 10_000
"""Threshold above which extreme concurrency optimizations are enabled."""

BATCH_PROCESSING_SIZE = 1000
"""Number of messages to process in batches for better throughput."""

LOCK_FREE_QUEUE_SIZE = 1_000_000
"""Size for lock-free queue implementations."""

DEFAULT_SERVICE_REGISTRATION_TIMEOUT = 30.0
"""Default timeout for service registration in seconds."""

DEFAULT_SERVICE_START_TIMEOUT = 30.0
"""Default timeout for service start in seconds."""

DEFAULT_COMMAND_RESPONSE_TIMEOUT = 30.0
"""Default timeout for command responses in seconds."""

DEFAULT_CONNECTION_PROBE_INTERVAL = 0.1
"""Default interval for connection probes in seconds until a response is received."""

DEFAULT_CONNECTION_PROBE_TIMEOUT = 30.0
"""Maximum amount of time to wait for connection probe response."""

DEFAULT_PROFILE_CONFIGURE_TIMEOUT = 300.0
"""Default timeout for profile configure command in seconds."""

DEFAULT_PROFILE_START_TIMEOUT = 60.0
"""Default timeout for profile start command in seconds."""

DEFAULT_MAX_REGISTRATION_ATTEMPTS = 10
"""Default maximum number of registration attempts for component services before giving up."""

DEFAULT_REGISTRATION_INTERVAL = 1.0
"""Default interval between registration attempts in seconds for component services."""
