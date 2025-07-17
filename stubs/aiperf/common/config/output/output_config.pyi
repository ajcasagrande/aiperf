#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config.base_config import BaseConfig as BaseConfig
from aiperf.common.config.config_defaults import OutputDefaults as OutputDefaults

class OutputConfig(BaseConfig):
    artifact_directory: Annotated[Path, None, None]
