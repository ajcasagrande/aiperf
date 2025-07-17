#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.dataset_models import Conversation as Conversation
from aiperf.common.dataset_models import Text as Text
from aiperf.common.dataset_models import Turn as Turn
from aiperf.common.enums import CustomDatasetType as CustomDatasetType
from aiperf.common.factories import CustomDatasetFactory as CustomDatasetFactory
from aiperf.services.dataset.generator import PromptGenerator as PromptGenerator
from aiperf.services.dataset.loader.models import CustomData as CustomData
from aiperf.services.dataset.loader.models import TraceCustomData as TraceCustomData

class TraceDatasetLoader:
    filename: Incomplete
    prompt_generator: Incomplete
    def __init__(self, filename: str, prompt_generator: PromptGenerator) -> None: ...
    def load_dataset(self) -> dict[str, list[CustomData]]: ...
    def convert_to_conversations(
        self, data: dict[str, list[TraceCustomData]]
    ) -> list[Conversation]: ...
