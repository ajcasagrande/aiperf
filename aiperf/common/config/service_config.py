# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated

import cyclopts
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aiperf.common.config.config_defaults import ServiceDefaults
from aiperf.common.config.zmq_config import BaseZMQCommunicationConfig
from aiperf.common.enums import CommunicationBackend, ServiceRunType


class ServiceConfig(BaseSettings):
    """Base configuration for all services. It will be provided to all services during their __init__ function."""

    model_config = SettingsConfigDict(
        env_prefix="AIPERF_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    service_run_type: Annotated[
        ServiceRunType,
        Field(
            description="Type of service run (MULTIPROCESSING, KUBERNETES)",
        ),
        cyclopts.Parameter(
            name=("--run-type"),
        ),
    ] = ServiceDefaults.SERVICE_RUN_TYPE

    comm_backend: Annotated[
        CommunicationBackend,
        Field(
            description="Communication backend to use",
        ),
        cyclopts.Parameter(
            name=("--comm-backend"),
        ),
    ] = ServiceDefaults.COMM_BACKEND

    comm_config: Annotated[
        BaseZMQCommunicationConfig | None,
        Field(
            description="Communication configuration",
        ),
        cyclopts.Parameter(
            name=("--comm-config"),
        ),
    ] = ServiceDefaults.COMM_CONFIG

    heartbeat_timeout: Annotated[
        float,
        Field(
            description="Time in seconds after which a service is considered dead if no "
            "heartbeat received",
        ),
        cyclopts.Parameter(
            name=("--heartbeat-timeout"),
        ),
    ] = ServiceDefaults.HEARTBEAT_TIMEOUT

    registration_timeout: Annotated[
        float,
        Field(
            description="Time in seconds to wait for all required services to register",
        ),
        cyclopts.Parameter(
            name=("--registration-timeout"),
        ),
    ] = ServiceDefaults.REGISTRATION_TIMEOUT

    command_timeout: Annotated[
        float,
        Field(
            description="Default timeout for command responses",
        ),
        cyclopts.Parameter(
            name=("--command-timeout"),
        ),
    ] = ServiceDefaults.COMMAND_TIMEOUT

    heartbeat_interval: Annotated[
        float,
        Field(
            description="Interval in seconds between heartbeat messages",
        ),
        cyclopts.Parameter(
            name=("--heartbeat-interval"),
        ),
    ] = ServiceDefaults.HEARTBEAT_INTERVAL

    min_workers: Annotated[
        int | None,
        Field(
            description="Minimum number of workers to maintain",
        ),
        cyclopts.Parameter(
            name=("--min-workers"),
        ),
    ] = ServiceDefaults.MIN_WORKERS

    max_workers: Annotated[
        int | None,
        Field(
            description="Maximum number of workers to create. If not specified, the number of"
            " workers will be determined by the smaller of (concurrency + 1) and (num CPUs - 1).",
        ),
        cyclopts.Parameter(
            name=("--max-workers"),
        ),
    ] = ServiceDefaults.MAX_WORKERS
