#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel

ADD_TO_TEMPLATE: str

class BaseConfig(AIPerfBaseModel):
    def serialize_to_yaml(self, verbose: bool = False, indent: int = 4) -> str: ...
