# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic_settings import BaseSettings, SettingsConfigDict

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig


class AIPerfConfig(BaseSettings):
    """Configuration for AIPerf. This is the top-level configuration for AIPerf."""

    model_config = SettingsConfigDict(
        env_prefix="AIPERF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    service: ServiceConfig
    user: UserConfig
