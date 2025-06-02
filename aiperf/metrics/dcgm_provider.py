import asyncio
from aiperf.common.enums import MetricProviders
from aiperf.common.factories import MetricProviderFactory
from aiperf.common.hooks import aiperf_task
from aiperf.common.metrics import BaseMetricProvider


@MetricProviderFactory.register(MetricProviders.NVIDIA_DCGM)
class DCGMProvider(BaseMetricProvider):
    """DCGM provider."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.metrics_1 = 0
        self.metrics_2 = 0
        self.metrics_3 = 0

    @aiperf_task
    async def _poll_metric_1(self) -> None:
        """Run the DCGM provider."""
        self.logger.debug("Running DCGM provider")
        while not self.stop_event.is_set():
            # start the metrics endpoint polling
            await asyncio.sleep(1)
            self.metrics_1 += 1

    @aiperf_task
    async def _poll_metric_2(self) -> None:
        """Run the DCGM provider."""
        self.logger.debug("Running DCGM provider")
        while not self.stop_event.is_set():
            # start the metrics endpoint polling
            await asyncio.sleep(1)
            self.metrics_2 += 1

    @aiperf_task
    async def _poll_metric_3(self) -> None:
        """Run the DCGM provider."""
        self.logger.debug("Running DCGM provider")
        while not self.stop_event.is_set():
            # start the metrics endpoint polling
            await asyncio.sleep(1)
            self.metrics_3 += 1

    def get_metrics(self) -> dict:
        """Get the metrics for the service."""
        return {
            "metrics_1": self.metrics_1,
            "metrics_2": self.metrics_2,
            "metrics_3": self.metrics_3,
        }

    def get_metrics_name(self) -> str:
        """Get the name of the metrics."""
        return "dcgm"
