#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import BeforeValidator as BeforeValidator
from pydantic import Field as Field

from aiperf.common.config.base_config import BaseConfig as BaseConfig
from aiperf.common.config.config_validators import (
    parse_str_or_list as parse_str_or_list,
)
from aiperf.common.config.endpoint.endpoint_config import (
    EndPointConfig as EndPointConfig,
)
from aiperf.common.config.input.input_config import InputConfig as InputConfig
from aiperf.common.config.loadgen_config import (
    LoadGeneratorConfig as LoadGeneratorConfig,
)
from aiperf.common.config.measurement_config import (
    MeasurementConfig as MeasurementConfig,
)
from aiperf.common.config.output.output_config import OutputConfig as OutputConfig
from aiperf.common.config.tokenizer.tokenizer_config import (
    TokenizerConfig as TokenizerConfig,
)

class UserConfig(BaseConfig):
    model_names: Annotated[list[str], None, None, None]
    endpoint: Annotated[EndPointConfig, None]
    input: Annotated[InputConfig, None]
    output: Annotated[OutputConfig, None]
    tokenizer: Annotated[TokenizerConfig, None]
    loadgen: Annotated[LoadGeneratorConfig, None]
    measurement: Annotated[MeasurementConfig, None]
