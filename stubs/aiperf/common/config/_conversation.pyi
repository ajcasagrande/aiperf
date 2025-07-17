#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import ConversationDefaults as ConversationDefaults
from aiperf.common.config._defaults import TurnDefaults as TurnDefaults
from aiperf.common.config._defaults import TurnDelayDefaults as TurnDelayDefaults

class TurnDelayConfig(BaseConfig):
    mean: Annotated[float, None, None]
    stddev: Annotated[float, None, None]
    ratio: Annotated[float, None, None]

class TurnConfig(BaseConfig):
    mean: Annotated[int, None, None]
    stddev: Annotated[int, None, None]
    delay: TurnDelayConfig

class ConversationConfig(BaseConfig):
    num: Annotated[int, None, None]
    turn: TurnConfig
