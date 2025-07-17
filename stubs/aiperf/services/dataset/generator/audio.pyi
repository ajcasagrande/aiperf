#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.config import AudioConfig as AudioConfig
from aiperf.common.enums import AudioFormat as AudioFormat
from aiperf.common.exceptions import ConfigurationError as ConfigurationError
from aiperf.services.dataset import utils as utils
from aiperf.services.dataset.generator.base import BaseGenerator as BaseGenerator

MP3_SUPPORTED_SAMPLE_RATES: Incomplete
SUPPORTED_BIT_DEPTHS: Incomplete

class AudioGenerator(BaseGenerator):
    config: Incomplete
    def __init__(self, config: AudioConfig) -> None: ...
    def generate(self, *args, **kwargs) -> str: ...
