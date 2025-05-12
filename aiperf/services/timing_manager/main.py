import asyncio
import sys
import time

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic, ClientType, ServiceState
from aiperf.common.models.base_models import BasePayload
from aiperf.common.models.credits import CreditDrop, CreditReturn
from aiperf.common.models.messages import BaseMessage
from aiperf.common.models.push_pull import PushPullData
from aiperf.common.service.component import ComponentServiceBase


class TimingManager(ComponentServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.TIMING_MANAGER, config=config)
        self._credits_available = 100
        self.logger.debug("Initializing timing manager")

    async def _initialize(self) -> None:
        """Initialize timing manager-specific components."""
        self.logger.debug("Initializing timing manager")
        # TODO: Implement timing manager initialization
        await self.communication.create_clients(
            ClientType.CREDIT_DROP_PUSH,
            ClientType.CREDIT_RETURN_PULL,
        )

    async def _on_start(self) -> None:
        """Start the timing manager."""
        self.logger.debug("Starting timing manager")
        # TODO: Implement timing manager start
        await self.communication.pull(
            ClientType.CREDIT_RETURN_PULL, Topic.CREDIT_RETURN, self._on_credit_return
        )
        self.state = ServiceState.RUNNING
        await asyncio.sleep(5)
        asyncio.create_task(self._issue_credit_drops())

    async def _issue_credit_drops(self) -> None:
        """Issue credit drops to workers."""
        self.logger.debug("Issuing credit drops to workers")
        # TODO: Actually implement real credit drop logic
        while self.state == ServiceState.RUNNING:
            try:
                await asyncio.sleep(0.1)
                if self._credits_available <= 0:
                    self.logger.warning("No credits available, skipping credit drop")
                    continue
                self.logger.debug("Issuing credit drop")
                # TODO: Actually implement real credit drop logic
                self._credits_available -= 1
                await self.communication.push(
                    ClientType.CREDIT_DROP_PUSH,
                    PushPullData(
                        topic=Topic.CREDIT_DROP,
                        source=self.service_id,
                        data=CreditDrop(
                            amount=1,
                            timestamp=time.time(),
                        ),
                    ),
                )
            except asyncio.CancelledError:
                self.logger.debug("Credit drop task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error issuing credit drop: {e}")
                await asyncio.sleep(0.1)

    async def _on_stop(self) -> None:
        """Stop the timing manager."""
        self.logger.debug("Stopping timing manager")
        # TODO: Implement timing manager stop

    async def _cleanup(self) -> None:
        """Clean up timing manager-specific components."""
        self.logger.debug("Cleaning up timing manager")
        # TODO: Implement timing manager cleanup

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")
        # TODO: Implement timing manager message processing

    async def _on_credit_return(self, pull_data: PushPullData) -> None:
        """Process a credit return message.

        Args:
            pull_data: The data received from the pull request
        """
        self.logger.debug(f"Processing credit return: {pull_data}")
        credit_return = CreditReturn.model_validate(pull_data.data)
        self._credits_available += credit_return.amount

    async def _configure(self, payload: BasePayload) -> None:
        """Configure the timing manager."""
        self.logger.debug(f"Configuring timing manager with payload: {payload}")
        # TODO: Implement timing manager configuration


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(TimingManager)


if __name__ == "__main__":
    sys.exit(main())
