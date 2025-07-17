#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import TokenizerDefaults as TokenizerDefaults

class TokenizerConfig(BaseConfig):
    name: Annotated[str | None, None, None]
    revision: Annotated[str, None, None]
    trust_remote_code: Annotated[bool, None, None]
