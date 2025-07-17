#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config.service_config import ServiceConfig as ServiceConfig
from aiperf.common.config.user_config import UserConfig as UserConfig

def load_service_config() -> ServiceConfig: ...
def load_user_config() -> UserConfig: ...
