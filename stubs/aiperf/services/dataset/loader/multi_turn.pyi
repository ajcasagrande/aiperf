#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.enums import CustomDatasetType as CustomDatasetType
from aiperf.common.factories import CustomDatasetFactory as CustomDatasetFactory
from aiperf.services.dataset.loader.models import CustomData as CustomData

class MultiTurnDatasetLoader:
    filename: Incomplete
    def __init__(self, filename: str) -> None: ...
    def load_dataset(self) -> dict[str, list[CustomData]]: ...
