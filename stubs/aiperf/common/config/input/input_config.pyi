#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Annotated, Any

from _typeshed import Incomplete
from typing_extensions import Self

from aiperf.common.config._audio import AudioConfig as AudioConfig
from aiperf.common.config._base import BaseConfig as BaseConfig
from aiperf.common.config._conversation import (
    ConversationConfig as ConversationConfig,
)
from aiperf.common.config._image import ImageConfig as ImageConfig
from aiperf.common.config._prompt import PromptConfig as PromptConfig
from aiperf.common.enums import CustomDatasetType as CustomDatasetType

logger: Incomplete

class InputConfig(BaseConfig):
    fixed_schedule: bool
    def validate_fixed_schedule(self) -> Self: ...
    extra: Annotated[dict[str, Any] | None, None, None, None]
    goodput: Annotated[dict[str, Any], None, None, None]
    headers: Annotated[dict[str, str] | None, None, None, None]
    file: Annotated[Any, None, None, None]
    custom_dataset_type: Annotated[CustomDatasetType, None, None]
    random_seed: Annotated[int | None, None, None]
    audio: AudioConfig
    image: ImageConfig
    prompt: PromptConfig
    conversation: ConversationConfig
