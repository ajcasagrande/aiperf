# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.core.base_service import BaseService


class ComponentService(BaseService):
    """A service that manages a component."""

    def __init__(self, service_id: str | None = None, **kwargs):
        super().__init__(service_id=service_id, **kwargs)
