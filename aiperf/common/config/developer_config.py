# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated

import cyclopts
from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aiperf.common.config.config_defaults import ServiceDefaults
from aiperf.common.config.config_validators import parse_service_types
from aiperf.common.config.groups import Groups
from aiperf.common.enums import ServiceType


class DeveloperConfig(BaseSettings):
    """Configuration for developer-only settings."""

    model_config = SettingsConfigDict(
        env_prefix="AIPERF_DEV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    _CLI_GROUP = Groups.DEVELOPER

    enable_yappi: Annotated[
        bool,
        Field(
            description="[red][Developer use only][/red] Enable yappi profiling (Yet Another Python Profiler) to profile AIPerf's internal python code. "
            "This can be used in the development of AIPerf in order to find performance bottlenecks across the various services. "
            "The output '.prof' files can be viewed with snakeviz. Requires yappi and snakeviz to be installed. "
            "Run 'pip install yappi snakeviz' to install them.",
        ),
        cyclopts.Parameter(
            name=("--enable-yappi-profiling"),
            group=_CLI_GROUP,
        ),
    ] = ServiceDefaults.ENABLE_YAPPI

    debug_services: Annotated[
        set[ServiceType] | None,
        Field(
            description="List of services to enable debug logging for. Can be a comma-separated list, a single service type, "
            "or the cli flag can be used multiple times.",
        ),
        cyclopts.Parameter(
            name=("--debug-service", "--debug-services"),
            group=_CLI_GROUP,
        ),
        BeforeValidator(parse_service_types),
    ] = ServiceDefaults.DEBUG_SERVICES

    trace_services: Annotated[
        set[ServiceType] | None,
        Field(
            description="List of services to enable trace logging for. Can be a comma-separated list, a single service type, "
            "or the cli flag can be used multiple times.",
        ),
        cyclopts.Parameter(
            name=("--trace-service", "--trace-services"),
            group=_CLI_GROUP,
        ),
        BeforeValidator(parse_service_types),
    ] = ServiceDefaults.TRACE_SERVICES
