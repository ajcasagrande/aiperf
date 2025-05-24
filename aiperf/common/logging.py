#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import logging
from typing import Any


class TraceLogger(logging.Logger):
    """Logger with TRACE level support."""

    TRACE_LEVEL = 5

    def __init_subclass__(cls) -> None:
        logging.TRACE = cls.TRACE_LEVEL
        # Set up TRACE level once
        logging.addLevelName(cls.TRACE_LEVEL, "TRACE")

        return super().__init_subclass__()

    def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(self.TRACE_LEVEL):
            self._log(self.TRACE_LEVEL, message, args, **kwargs)
