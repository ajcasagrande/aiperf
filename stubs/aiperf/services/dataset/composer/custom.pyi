#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import InputConfig as InputConfig
from aiperf.common.enums import ComposerType as ComposerType
from aiperf.common.enums import CustomDatasetType as CustomDatasetType
from aiperf.common.factories import ComposerFactory as ComposerFactory
from aiperf.common.factories import CustomDatasetFactory as CustomDatasetFactory
from aiperf.common.models import Conversation as Conversation
from aiperf.common.tokenizer import Tokenizer as Tokenizer
from aiperf.services.dataset import utils as utils
from aiperf.services.dataset.composer.base import (
    BaseDatasetComposer as BaseDatasetComposer,
)

class CustomDatasetComposer(BaseDatasetComposer):
    def __init__(self, config: InputConfig, tokenizer: Tokenizer) -> None: ...
    def create_dataset(self) -> list[Conversation]: ...
