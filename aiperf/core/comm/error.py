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
from aiperf.core.comm.enum import CommState
from aiperf.core.error import AIPerfError, StateError


class CommError(AIPerfError):
    """Base class for communication errors."""


class CommChannelError(CommError):
    """Error with communication channel operations."""

    def __init__(self, message: str = "", operation: str | None = None) -> None:
        """
        Args:
            message: Error details
            operation: Optional operation that failed (publish, subscribe, etc)
        """
        # TODO: Support enums for operation
        op_msg = f" while {operation}" if operation else ""
        super().__init__(f"{message}{op_msg}")
        self.operation = operation


class CommStateError(StateError, CommError):
    """Error when a communication component is in incorrect state."""

    def __init__(
        self,
        message: str = "",
        expected_state: CommState | str | None = None,
        actual_state: CommState | str | None = None,
        channel: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            expected_state=expected_state,
            actual_state=actual_state,
            component=channel or "communication channel",
        )
        self.channel = channel
