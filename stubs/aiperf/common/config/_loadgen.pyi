#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import (
    LoadGeneratorDefaults as LoadGeneratorDefaults,
)
from aiperf.common.enums import RequestRateMode as RequestRateMode

class LoadGeneratorConfig(BaseConfig):
    concurrency: Annotated[int, None, None]
    request_rate: Annotated[float | None, None, None]
    request_rate_mode: Annotated[RequestRateMode, None, None]
    request_count: Annotated[int, None, None]
    warmup_request_count: Annotated[int, None, None]
