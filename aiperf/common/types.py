# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any, TypeVar

ConfigT = TypeVar("ConfigT", bound=Any, covariant=True)
RequestT = TypeVar("RequestT", bound=Any)
ResponseT = TypeVar("ResponseT", bound=Any, covariant=True)
RawResponseT = TypeVar("RawResponseT", bound=Any, contravariant=True)
InputT = TypeVar("InputT", bound=Any)
OutputT = TypeVar("OutputT", bound=Any)
RawRequestT = TypeVar("RawRequestT", bound=Any, contravariant=True)
