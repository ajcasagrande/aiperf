#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod

from _typeshed import Incomplete

from aiperf.common.config._input import InputConfig as InputConfig
from aiperf.common.models import Conversation as Conversation
from aiperf.common.tokenizer import Tokenizer as Tokenizer
from aiperf.services.dataset.generator import AudioGenerator as AudioGenerator
from aiperf.services.dataset.generator import ImageGenerator as ImageGenerator
from aiperf.services.dataset.generator import PromptGenerator as PromptGenerator

class BaseDatasetComposer(ABC, metaclass=abc.ABCMeta):
    config: Incomplete
    logger: Incomplete
    prompt_generator: Incomplete
    image_generator: Incomplete
    audio_generator: Incomplete
    def __init__(self, config: InputConfig, tokenizer: Tokenizer) -> None: ...
    @abstractmethod
    def create_dataset(self) -> list[Conversation]: ...
    @property
    def prefix_prompt_enabled(self) -> bool: ...
