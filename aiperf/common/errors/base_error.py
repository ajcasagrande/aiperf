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
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field


class Error(BaseModel):
    """Base model for all errors."""

    # Allow arbitrary types for error details and exception info
    model_config = ConfigDict(arbitrary_types_allowed=True)

    error_message: str | None = Field(
        None, description="The error message, if applicable"
    )
    error_code: int | None = Field(None, description="The error code, if applicable")
    error_details: dict[str, Any] | None = Field(
        None, description="Additional details about the error"
    )
    exception: BaseException | None = Field(
        None, description="The exception that caused the error, if applicable"
    )

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}: {self.error_message} "
            f"{self.error_details or ''}"
        )

    @classmethod
    def from_exception(cls, exception: BaseException) -> Self:
        """Create a new error object from an exception.

        Args:
            exception: The exception to create the error from.

        Returns:
            A new error object based on the class this method is called on.
        """
        return cls(
            error_message=str(exception),
            exception=exception,
        )
