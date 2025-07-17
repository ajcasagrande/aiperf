#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.config import PromptConfig as PromptConfig
from aiperf.common.exceptions import DatasetGeneratorError as DatasetGeneratorError
from aiperf.common.exceptions import InvalidStateError as InvalidStateError
from aiperf.common.exceptions import NotInitializedError as NotInitializedError
from aiperf.common.tokenizer import Tokenizer as Tokenizer
from aiperf.services.dataset import utils as utils
from aiperf.services.dataset.generator.base import BaseGenerator as BaseGenerator

logger: Incomplete
DEFAULT_CORPUS_FILE: str

class PromptGenerator(BaseGenerator):
    config: Incomplete
    tokenizer: Incomplete
    def __init__(self, config: PromptConfig, tokenizer: Tokenizer) -> None: ...
    def generate(
        self,
        mean: int | None = None,
        stddev: int | None = None,
        hash_ids: list[int] | None = None,
    ) -> str: ...
    def get_random_prefix_prompt(self) -> str: ...
