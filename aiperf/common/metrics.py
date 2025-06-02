from abc import abstractmethod

from aiperf.common.hooks import AIPerfTaskMixin


class BaseMetricProvider(AIPerfTaskMixin):
    """Base class for all metric providers."""

    @abstractmethod
    def get_metrics(self) -> dict:
        """Get the metrics for the service."""
        pass

    @abstractmethod
    def get_metrics_name(self) -> str:
        """Get the name of the metrics."""
