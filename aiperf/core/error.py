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
from aiperf.core.enum import StrEnum


class AIPerfError(Exception):
    """Base exception for all AIPerf errors."""

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {super().__str__()}"


class MultiError(AIPerfError):
    """Container for multiple errors that occurred during an operation."""

    def __init__(
        self,
        exceptions: list[Exception],
        operation: str | None = None,
    ) -> None:
        """
        Args:
            exceptions: List of exceptions that occurred
            operation: Optional name of the operation that generated multiple errors
        """
        operation_message = f" during {operation}" if operation else ""
        message = f"{len(exceptions)} errors occurred{operation_message}"
        super().__init__(message)

        self.exceptions = exceptions
        self.operation = operation

    def __str__(self) -> str:
        """Format the multi-error with details of contained exceptions."""
        base = super().__str__()
        details = "\n".join(f"  - {e}" for e in self.exceptions)
        return f"{base}:\n{details}"


# Base state error with shared functionality
class StateError(AIPerfError):
    """Error when component is in incorrect state for an operation."""

    def __init__(
        self,
        message: str = "",
        expected_state: StrEnum | str | None = None,
        actual_state: StrEnum | str | None = None,
        component: str | None = None,
    ) -> None:
        """
        Args:
            message: Error details
            expected_state: State that was expected
            actual_state: Actual state encountered
            component: Optional component name/identifier
        """
        component_message = f" in {component}" if component else ""
        state_message = ""
        if expected_state is not None:
            state_message = f" Expected state '{expected_state!r}'"
            if actual_state is not None:
                state_message += f", got '{actual_state!r}'"

        super().__init__(f"{message}{component_message}{state_message}")

        self.expected_state = expected_state
        self.actual_state = actual_state
        self.component = component


class RegistrationError(AIPerfError):
    """Error when something fails to register."""

    def __init__(self, message: str = "", component: str | None = None) -> None:
        super().__init__(message)
        self.component = component
