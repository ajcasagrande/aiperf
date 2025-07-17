#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import TypeVar

from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel

BaseModelT = TypeVar("BaseModelT", bound="AIPerfBaseModel")

def exclude_if_none(field_names: list[str]): ...

class ExcludeIfNoneMixin(AIPerfBaseModel): ...
