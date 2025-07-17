#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Literal

from _typeshed import Incomplete

from aiperf.common.enums import CustomDatasetType as CustomDatasetType
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel

class TraceCustomData(AIPerfBaseModel):
    type: Literal[CustomDatasetType.TRACE]
    input_length: int
    output_length: int
    hash_ids: list[int]
    timestamp: int | None
    session_id: str | None
    delay: int | None
    def validate_mutually_exclusive_fields(self) -> TraceCustomData: ...

CustomData: Incomplete
