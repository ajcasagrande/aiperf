# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.metric_enums import (
    EnergyMetricUnit,
    FrequencyMetricUnit,
    GenericMetricUnit,
    MetricFlags,
    MetricSizeUnit,
    MetricTimeUnit,
    MetricUnitT,
    PowerMetricUnit,
    TemperatureMetricUnit,
)
from aiperf.common.models import TelemetryRecord
from aiperf.metrics.base_telemetry_metric import BaseTelemetryMetric

GPU_TELEMETRY_METRICS_CONFIG = [
    ("GPU Power Usage", "gpu_power_usage", PowerMetricUnit.WATT),
    ("Energy Consumption", "energy_consumption", EnergyMetricUnit.MEGAJOULE),
    ("GPU Utilization", "gpu_utilization", GenericMetricUnit.PERCENT),
    ("Memory Copy Utilization", "memory_copy_utilization", GenericMetricUnit.PERCENT),
    ("GPU Memory Used", "gpu_memory_used", MetricSizeUnit.GIGABYTES),
    ("SM Clock Frequency", "sm_clock_frequency", FrequencyMetricUnit.MEGAHERTZ),
    ("Memory Clock Frequency", "memory_clock_frequency", FrequencyMetricUnit.MEGAHERTZ),
    ("Memory Temperature", "memory_temperature", TemperatureMetricUnit.CELSIUS),
    ("GPU Temperature", "gpu_temperature", TemperatureMetricUnit.CELSIUS),
    ("XID Errors", "xid_errors", GenericMetricUnit.COUNT),
    ("Power Violation", "power_violation", MetricTimeUnit.MICROSECONDS),
    ("Thermal Violation", "thermal_violation", MetricTimeUnit.MICROSECONDS),
]

def create_telemetry_metric(display_name: str, metric_key: str, unit_: MetricUnitT) -> type[BaseTelemetryMetric[float]]:
    class TelemetryMetric(BaseTelemetryMetric[float]):
        tag = metric_key
        header = display_name
        unit = unit_
        display_order = None
        required_metrics = None
        flags = MetricFlags.GPU_TELEMETRY

        def _extract_value(self, record: TelemetryRecord) -> float | None:
            return getattr(record.telemetry_data, metric_key)

    TelemetryMetric.__name__ = f"{display_name.replace(' ', '').replace('-', '')}Metric"
    TelemetryMetric.__qualname__ = TelemetryMetric.__name__
    TelemetryMetric.__doc__ = f"{display_name} metric from GPU telemetry."
    return TelemetryMetric


for display_name, metric_key, unit in GPU_TELEMETRY_METRICS_CONFIG:
    create_telemetry_metric(display_name, metric_key, unit)
