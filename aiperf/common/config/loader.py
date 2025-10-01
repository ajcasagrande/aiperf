# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig


def load_service_config() -> ServiceConfig:
    """Load the service configuration."""
    # TODO: Ensure this works by loading env variables
    return ServiceConfig()


def load_user_config() -> UserConfig:
    """Load the user configuration."""
    # TODO: implement
    raise NotImplementedError("User configuration is not implemented")
