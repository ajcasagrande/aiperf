#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from abc import abstractmethod

from aiperf.common.mixins import AIPerfTaskMixin


class BaseMetricProvider(AIPerfTaskMixin):
    """Base class for all metric providers."""

    @abstractmethod
    def get_metrics(self) -> dict:
        """Get the metrics for the service."""
        pass
