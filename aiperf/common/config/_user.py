# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated

import cyclopts
from pydantic import BeforeValidator, Field

from aiperf.common.config._base import BaseConfig
from aiperf.common.config._endpoint import EndPointConfig
from aiperf.common.config._input import InputConfig
from aiperf.common.config._loadgen import LoadGeneratorConfig
from aiperf.common.config._output import OutputConfig
from aiperf.common.config._tokenizer import TokenizerConfig
from aiperf.common.config._validators import (
    parse_str_or_list,
)


class UserConfig(BaseConfig):
    """
    A configuration class for defining top-level user settings.
    """

    model_names: Annotated[
        list[str],
        Field(
            ...,
            description="Model name(s) to be benchmarked. Can be a comma-separated list or a single model name.",
        ),
        BeforeValidator(parse_str_or_list),
        cyclopts.Parameter(
            name=(
                "--model-names",
                "--model",  # GenAI-Perf
                "-m",  # GenAI-Perf
            ),
            group="Endpoint",
        ),
    ]

    endpoint: Annotated[
        EndPointConfig,
        Field(
            description="Endpoint configuration",
        ),
    ] = EndPointConfig()

    input: Annotated[
        InputConfig,
        Field(
            description="Input configuration",
        ),
    ] = InputConfig()

    output: Annotated[
        OutputConfig,
        Field(
            description="Output configuration",
        ),
    ] = OutputConfig()

    tokenizer: Annotated[
        TokenizerConfig,
        Field(
            description="Tokenizer configuration",
        ),
    ] = TokenizerConfig()

    loadgen: Annotated[
        LoadGeneratorConfig,
        Field(
            description="Load Generator configuration",
        ),
    ] = LoadGeneratorConfig()

    # measurement: Annotated[
    #     MeasurementConfig,
    #     Field(
    #         description="Measurement configuration",
    #     ),
    # ] = MeasurementConfig()
