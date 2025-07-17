#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._endpoint import (
    EndPointConfig as EndPointConfig,
)
from aiperf.common.config._input import InputConfig as InputConfig
from aiperf.common.config._loadgen import (
    LoadGeneratorConfig as LoadGeneratorConfig,
)
from aiperf.common.config._output import OutputConfig as OutputConfig
from aiperf.common.config._tokenizer import (
    TokenizerConfig as TokenizerConfig,
)

class UserConfig(BaseConfig):
    model_names: Annotated[list[str], None, None, None]
    endpoint: Annotated[EndPointConfig, None]
    input: Annotated[InputConfig, None]
    output: Annotated[OutputConfig, None]
    tokenizer: Annotated[TokenizerConfig, None]
    loadgen: Annotated[LoadGeneratorConfig, None]
