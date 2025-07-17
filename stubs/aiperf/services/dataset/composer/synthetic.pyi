#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import InputConfig as InputConfig
from aiperf.common.enums import ComposerType as ComposerType
from aiperf.common.factories import ComposerFactory as ComposerFactory
from aiperf.common.models import Audio as Audio
from aiperf.common.models import Conversation as Conversation
from aiperf.common.models import Image as Image
from aiperf.common.models import Text as Text
from aiperf.common.models import Turn as Turn
from aiperf.common.tokenizer import Tokenizer as Tokenizer
from aiperf.services.dataset import utils as utils
from aiperf.services.dataset.composer.base import (
    BaseDatasetComposer as BaseDatasetComposer,
)

class SyntheticDatasetComposer(BaseDatasetComposer):
    def __init__(self, config: InputConfig, tokenizer: Tokenizer) -> None: ...
    def create_dataset(self) -> list[Conversation]: ...
    @property
    def include_prompt(self) -> bool: ...
    @property
    def include_image(self) -> bool: ...
    @property
    def include_audio(self) -> bool: ...
