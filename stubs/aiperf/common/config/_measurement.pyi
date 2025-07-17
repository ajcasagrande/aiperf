#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import MeasurementDefaults as MeasurementDefaults

class MeasurementConfig(BaseConfig):
    measurement_interval: Annotated[float, None, None]
    stability_percentage: Annotated[float, None, None]
