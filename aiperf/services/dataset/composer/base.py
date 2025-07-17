# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod

from aiperf.common.config._input import InputConfig
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Conversation
from aiperf.common.tokenizer import Tokenizer
from aiperf.services.dataset.generator import (
    AudioGenerator,
    ImageGenerator,
    PromptGenerator,
)


class BaseDatasetComposer(AIPerfLoggerMixin, ABC):
    def __init__(self, config: InputConfig, tokenizer: Tokenizer):
        super().__init__()
        self.config = config

        self.prompt_generator = PromptGenerator(config.prompt, tokenizer)
        self.image_generator = ImageGenerator(config.image)
        self.audio_generator = AudioGenerator(config.audio)

    @abstractmethod
    def create_dataset(self) -> list[Conversation]:
        """
        Create a set of conversation objects from the given configuration.

        Returns:
            list[Conversation]: A list of conversation objects.
        """
        ...

    @property
    def prefix_prompt_enabled(self) -> bool:
        return self.config.prompt.prefix_prompt.length > 0
