# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import uuid
from typing import ClassVar

from aiperf.common.enums.service_enums import ServiceType
from aiperf.core.background_tasks import BackgroundTasksMixin
from aiperf.core.communication_mixins import MessageBusMixin
from aiperf.core.profile_lifecycle import ProfileLifecycle


class BaseService(ProfileLifecycle, MessageBusMixin, BackgroundTasksMixin):
    """A base class for all services."""

    service_type: ClassVar[ServiceType | str]

    def __init__(self, service_id: str | None = None, **kwargs):
        self.service_id = (
            service_id or f"{self.service_type}_{str(uuid.uuid4().hex)[:8]}"
        )
        super().__init__(service_id=self.service_id, id=self.service_id, **kwargs)

    def __str__(self):
        return f"{self.service_type} {self.service_id}"

    def __repr__(self):
        return f"<{self.service_type} {self.service_id}>"
