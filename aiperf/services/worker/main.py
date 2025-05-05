import sys
from typing import Any, Dict

from aiperf.common.config.service_config import WorkerConfig


class Worker:
    """Worker responsible for sending requests to the server."""

    def __init__(self, config: WorkerConfig):
        self.config = config

    async def start(self) -> None:
        """Start the worker."""

    async def stop(self) -> None:
        """Stop the worker."""

    async def process_credit(self, credit_data: Dict[str, Any]) -> None:
        """Process a credit by initiating a conversation."""

    async def handle_conversation(self, conversation_data: Dict[str, Any]) -> None:
        """Handle a conversation with the server."""

    async def send_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the server."""

    async def publish_result(self, result_data: Dict[str, Any]) -> None:
        """Publish a result to the worker manager."""


if __name__ == "__main__":
    import uvloop

    uvloop.install()

    # Load the service configuration
    from aiperf.common.config.loader import load_worker_config

    cfg = load_worker_config()
    worker = Worker(cfg)
    sys.exit(uvloop.run(worker.run()))
