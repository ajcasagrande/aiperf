#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from aiperf.common.enums import MetricTimeType as MetricTimeType
from aiperf.common.exceptions import MetricTypeError as MetricTypeError
from aiperf.common.record_models import ParsedResponseRecord as ParsedResponseRecord

class BaseMetric(ABC, metaclass=abc.ABCMeta):
    tag: ClassVar[str]
    unit: ClassVar[MetricTimeType]
    larger_is_better: ClassVar[bool]
    header: ClassVar[str]
    streaming_only: ClassVar[bool]
    metric_interfaces: dict[str, type[BaseMetric]]
    def __init_subclass__(cls, **kwargs) -> None: ...
    @classmethod
    def get_all(cls) -> dict[str, type[BaseMetric]]: ...
    @abstractmethod
    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[str, BaseMetric] | None = None,
    ) -> None: ...
    @abstractmethod
    def values(self) -> Any: ...
    def get_converted_metrics(self, unit: MetricTimeType) -> list[Any]: ...
