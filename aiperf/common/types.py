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
from typing import Any, TypeVar

# Prevent exporting other imported types
__all__ = [
    "ConfigT",
    "RequestT",
    "ResponseT",
]

ConfigT = TypeVar("ConfigT", bound=Any, infer_variance=True)
RequestT = TypeVar("RequestT", bound=Any, infer_variance=True)
ResponseT = TypeVar("ResponseT", bound=Any, infer_variance=True)
InputT = TypeVar("InputT", bound=Any, infer_variance=True)
OutputT = TypeVar("OutputT", bound=Any, infer_variance=True)
