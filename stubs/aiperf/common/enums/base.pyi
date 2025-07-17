#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from enum import Enum
from typing import Any

class CaseInsensitiveStrEnum(str, Enum):
    def __eq__(self, other: Any) -> bool: ...
    def __hash__(self) -> int: ...
