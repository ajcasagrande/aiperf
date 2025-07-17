#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums.base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class AIPerfUIType(CaseInsensitiveStrEnum):
    RICH = "rich"
    TEXTUAL = "textual"
    BASIC = "basic"
    NONE = "none"
    @property
    def is_graphical(self) -> bool: ...
