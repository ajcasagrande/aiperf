#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from pydantic import Field as Field

from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._defaults import ImageDefaults as ImageDefaults
from aiperf.common.enums import ImageFormat as ImageFormat

class ImageHeightConfig(BaseConfig):
    mean: Annotated[float, None, None]
    stddev: Annotated[float, None, None]

class ImageWidthConfig(BaseConfig):
    mean: Annotated[float, None, None]
    stddev: Annotated[float, None, None]

class ImageConfig(BaseConfig):
    width: ImageWidthConfig
    height: ImageHeightConfig
    batch_size: Annotated[int, None, None]
    format: Annotated[ImageFormat, None, None]
