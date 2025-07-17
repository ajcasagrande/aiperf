#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import WorkerDefaults as WorkerDefaults

class WorkersConfig(BaseConfig):
    min: Annotated[int | None, None, None]
    max: Annotated[int | None, None, None]
    health_check_interval_seconds: Annotated[float, None, None]
