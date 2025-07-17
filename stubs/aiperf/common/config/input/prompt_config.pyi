#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config.base_config import BaseConfig as BaseConfig
from aiperf.common.config.config_defaults import (
    InputTokensDefaults as InputTokensDefaults,
)
from aiperf.common.config.config_defaults import (
    OutputTokensDefaults as OutputTokensDefaults,
)
from aiperf.common.config.config_defaults import (
    PrefixPromptDefaults as PrefixPromptDefaults,
)
from aiperf.common.config.config_defaults import PromptDefaults as PromptDefaults

class InputTokensConfig(BaseConfig):
    mean: Annotated[int, None, None]
    stddev: Annotated[float, None, None]
    block_size: Annotated[int, None, None]

class OutputTokensConfig(BaseConfig):
    mean: Annotated[int, None, None]
    deterministic: Annotated[bool, None, None]
    stddev: Annotated[float, None, None]

class PrefixPromptConfig(BaseConfig):
    pool_size: Annotated[int, None, None]
    length: Annotated[int, None, None]

class PromptConfig(BaseConfig):
    batch_size: Annotated[int, None, None]
    input_tokens: InputTokensConfig
    output_tokens: OutputTokensConfig
    prefix_prompt: PrefixPromptConfig
