#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import BeforeValidator as BeforeValidator
from pydantic import Field as Field

from aiperf.common.config.base_config import BaseConfig as BaseConfig
from aiperf.common.config.config_defaults import AudioDefaults as AudioDefaults
from aiperf.common.config.config_validators import (
    parse_str_or_list_of_positive_values as parse_str_or_list_of_positive_values,
)
from aiperf.common.enums import AudioFormat as AudioFormat

class AudioLengthConfig(BaseConfig):
    mean: Annotated[float, None, None]
    stddev: Annotated[float, None, None]

class AudioConfig(BaseConfig):
    batch_size: Annotated[int, None, None]
    length: AudioLengthConfig
    format: Annotated[AudioFormat, None, None]
    depths: Annotated[list[int], None, None, None]
    sample_rates: Annotated[list[float], None, None, None]
    num_channels: Annotated[int, None, None]
