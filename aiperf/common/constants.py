# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

NANOS_PER_SECOND = 1_000_000_000
NANOS_PER_MILLIS = 1_000_000
BYTES_PER_MIB = 1024 * 1024

GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 5.0

################################################################################
# Environment Defaults
################################################################################


class EnvDefaults:
    """Default values for the AIPerf environment variables."""

    AIPERF_UVLOOP = 1
    AIPERF_LOG_LEVEL = "INFO"
    AIPERF_DISABLE_UI = "false"
