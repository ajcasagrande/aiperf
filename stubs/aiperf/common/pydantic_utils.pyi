#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any, TypeVar

from _typeshed import Incomplete
from pydantic import BaseModel

BaseModelT = TypeVar("BaseModelT", bound="AIPerfBaseModel")

class AIPerfBaseModel(BaseModel):
    model_config: Incomplete
    def __init__(self, **kwargs: Any) -> None: ...

def exclude_if_none(field_names: list[str]): ...

class ExcludeIfNoneMixin(AIPerfBaseModel): ...
