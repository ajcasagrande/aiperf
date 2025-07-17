#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config import UserConfig as UserConfig

def run_system_controller(
    user_config: UserConfig, service_config: ServiceConfig
) -> None: ...
def warn_command_not_implemented(command: str) -> None: ...
