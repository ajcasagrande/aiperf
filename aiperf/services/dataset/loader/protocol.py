# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol, runtime_checkable

from aiperf.common.dataset_models import Conversation
from aiperf.services.dataset.loader.models import CustomData


@runtime_checkable
class CustomDatasetLoaderProtocol(Protocol):
    def load_dataset(self) -> dict[str, list[CustomData]]: ...

    def convert_to_conversations(
        self, custom_data: dict[str, list[CustomData]]
    ) -> list[Conversation]: ...
