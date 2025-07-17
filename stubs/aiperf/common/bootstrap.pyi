#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import multiprocessing

from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.config.user_config import UserConfig as UserConfig
from aiperf.common.service.base_service import BaseService as BaseService

def bootstrap_and_run_service(
    service_class: type[BaseService],
    service_config: ServiceConfig | None = None,
    user_config: UserConfig | None = None,
    service_id: str | None = None,
    log_queue: multiprocessing.Queue | None = None,
    **kwargs,
): ...
