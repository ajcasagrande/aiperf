# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class CommandType(CaseInsensitiveStrEnum):
    """List of commands that the SystemController can send to component services."""

    SHUTDOWN = "shutdown"
    """A command sent to shutdown a service. This will stop the service gracefully
    no matter what state it is in."""

    PROCESS_RECORDS = "process_records"
    """A command sent to process records. This will process the records and return
    the services to their pre-record processing state."""

    CONFIGURE_PROFILING = "configure_profiling"
    """A command sent to configure a service in preparation for a profile run. This will
    override the current configuration."""

    START_PROFILING = "start_profiling"
    """A command sent to indicate that a service should begin profiling using the
    current configuration."""

    STOP_PROFILING = "stop_profiling"
    """A command sent to indicate that a service should stop doing profile related
    work, as the profile run is complete."""

    CANCEL_PROFILING = "cancel_profiling"
    """A command sent to cancel a profile run. This will stop the current profile run and
    process the partial results."""


class CommandResponseStatus(CaseInsensitiveStrEnum):
    """Status of a command response."""

    ACKNOWLEDGED = "acknowledged"
    SUCCESS = "success"
    FAILURE = "failure"
