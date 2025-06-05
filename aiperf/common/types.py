#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any, TypeVar

ConfigT = TypeVar("ConfigT", bound=Any, infer_variance=True)
RequestT = TypeVar("RequestT", bound=Any, infer_variance=True)
ResponseT = TypeVar("ResponseT", bound=Any, infer_variance=True)
InputT = TypeVar("InputT", bound=Any, infer_variance=True)
OutputT = TypeVar("OutputT", bound=Any, infer_variance=True)
