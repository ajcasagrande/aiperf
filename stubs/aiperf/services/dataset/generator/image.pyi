#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.config import ImageConfig as ImageConfig
from aiperf.common.enums import ImageFormat as ImageFormat
from aiperf.services.dataset import utils as utils
from aiperf.services.dataset.generator.base import BaseGenerator as BaseGenerator

class ImageGenerator(BaseGenerator):
    config: Incomplete
    def __init__(self, config: ImageConfig) -> None: ...
    def generate(self, *args, **kwargs) -> str: ...
