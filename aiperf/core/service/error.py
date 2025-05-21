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
from aiperf.core.error import AIPerfError
from aiperf.core.service.enum import ServiceState


class ServiceError(AIPerfError):
    """Base class for service-related errors."""


class ServiceLifecycleError(ServiceError):
    """Error during service lifecycle (init, start, stop, etc)."""

    def __init__(
        self, message: str = "", phase: ServiceState | str | None = None
    ) -> None:
        """
        Args:
            message: Error details
            phase: Optional lifecycle phase where error occurred
                   (init, start, stop, configure, etc)
        """
        # TODO: Support enums for phase
        phase_msg = f" during {phase}" if phase else ""
        super().__init__(f"{message}{phase_msg}")
        self.phase = phase
