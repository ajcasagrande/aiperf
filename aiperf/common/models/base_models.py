# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, ConfigDict


class AIPerfBaseModel(BaseModel):
    """Base model for all AIPerf Pydantic models. This class is configured to allow
    arbitrary types to be used as fields as to allow for more flexible model definitions
    by end users without breaking the existing code.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
