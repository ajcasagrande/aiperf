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
from pydantic import BaseModel, Field


class CreditDrop(BaseModel):
    """Model for a credit drop."""

    amount: int = Field(..., description="Amount of credits to drop")
    timestamp: float = Field(..., description="Timestamp of the credit drop")


class CreditDropResponse(BaseModel):
    """Model for a credit drop response."""

    success: bool = Field(..., description="Whether the credit drop was successful")
    message: str = Field(..., description="Message from the credit drop")


class CreditReturn(BaseModel):
    """Model for a credit return."""

    amount: int = Field(..., description="Amount of credits to return")


class CreditReturnResponse(BaseModel):
    """Model for a credit return response."""

    success: bool = Field(..., description="Whether the credit return was successful")
    message: str = Field(..., description="Message from the credit return")
