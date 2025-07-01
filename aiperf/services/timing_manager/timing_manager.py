# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import time

from aiperf.common.comms.base import (
    ClientAddressType,
    PullClient,
    PushClient,
    ReqClient,
)
from aiperf.common.config import ServiceConfig
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import (
    MessageType,
    NotificationType,
    ServiceState,
    ServiceType,
)
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.messages import (
    CreditDropMessage,
    CreditReturnMessage,
    CreditsCompleteMessage,
    DatasetTimingRequest,
    DatasetTimingResponse,
    Message,
    NotificationMessage,
    ProfileProgressMessage,
)
from aiperf.common.service.base_component_service import BaseComponentService


@ServiceFactory.register(ServiceType.TIMING_MANAGER)
class TimingManager(BaseComponentService):
    """
    The TimingManager service is responsible to generate the schedule and issuing
    timing credits for requests.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self._credit_lock = asyncio.Lock()

        self._total_credits = int(os.getenv("AIPERF_TOTAL_REQUESTS", 25))
        self._credits_available = min(
            self._total_credits, int(os.getenv("AIPERF_CONCURRENCY", 5))
        )

        self._sent_credits = 0
        self._completed_credits = 0
        self._credit_event = asyncio.Event()
        self.start_time_ns = 0
        self.logger.debug("Initializing timing manager")

        self.dataset_timing_response: DatasetTimingResponse | None = None
        self.dataset_ready: asyncio.Event = asyncio.Event()

        self.dataset_request_client: ReqClient = self.comms.create_req_client(
            ClientAddressType.DEALER_ROUTER_REQ_REP_FRONTEND,
        )
        self.credit_drop_client: PushClient = self.comms.create_push_client(
            ClientAddressType.CREDIT_DROP_PUSH_PULL,
            bind=True,
        )
        self.credit_return_client: PullClient = self.comms.create_pull_client(
            ClientAddressType.CREDIT_RETURN_PUSH_PULL,
            bind=True,
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.TIMING_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize timing manager-specific components."""
        self.logger.debug("Initializing timing manager")

        await self.credit_return_client.register_pull_callback(
            message_type=MessageType.CREDIT_RETURN,
            callback=self._on_credit_return,
        )
        await self.sub_client.subscribe(
            message_type=MessageType.NOTIFICATION,
            callback=self._on_notification,
        )

    @on_configure
    async def _configure(self, message: Message) -> None:
        """Configure the timing manager."""
        self.logger.debug(f"Configuring timing manager with message: {message}")
        # TODO: Implement timing manager configuration

    @on_start
    async def _start(self) -> None:
        """Start the timing manager."""
        self.logger.debug("Starting timing manager")
        # TODO: Implement timing manager start
        await self.set_state(ServiceState.RUNNING)

    @on_stop
    async def _stop(self) -> None:
        """Stop the timing manager."""
        self.logger.debug("Stopping timing manager")
        # TODO: Implement timing manager stop

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up timing manager-specific components."""
        self.logger.debug("Cleaning up timing manager")
        # TODO: Implement timing manager cleanup

    async def _on_notification(self, message: NotificationMessage) -> None:
        """Handle a notification message."""
        self.logger.info(f"TM: Received notification: {message.notification_type}")
        if message.notification_type == NotificationType.DATASET_CONFIGURED:
            self.logger.debug("TM: Requesting dataset timing information")
            self.dataset_timing_response = await self.dataset_request_client.request(
                message=DatasetTimingRequest(
                    service_id=self.service_id,
                ),
            )
            self.logger.debug(
                "TM: Received dataset timing response: %s",
                self.dataset_timing_response,
            )
            self.dataset_ready.set()

    @on_start
    async def _issue_credit_drops(self) -> None:
        """Issue credit drops to workers."""
        self.logger.debug("Issuing credit drops to workers")

        # TODO: Actually implement real credit drop logic
        await self.initialized_event.wait()

        self.logger.info("TM: Waiting for dataset to be ready")
        await self.dataset_ready.wait()
        self.logger.info("TM: Dataset is ready")

        self.start_time_ns = time.time_ns()

        await self.pub_client.publish(
            ProfileProgressMessage(
                service_id=self.service_id,
                start_ns=self.start_time_ns,
                total=self._total_credits,
                completed=self._completed_credits,
            ),
        )

        drop_at = time.time_ns() + 100_000

        self.logger.info("TM: Issuing credit drops")
        while not self.stop_event.is_set():
            try:
                if not self._credits_available:
                    self.logger.debug("Waiting for credit event")
                    self._credit_event.clear()
                    await self._credit_event.wait()
                    self.logger.debug("Credit event received")
                    continue

                self.logger.debug(
                    f"Issuing credit drop {self._sent_credits + 1} of {self._total_credits}"
                )

                async def drop_task():
                    await self.credit_drop_client.push(
                        message=CreditDropMessage(
                            service_id=self.service_id,
                            amount=1,
                            credit_drop_ns=drop_at,
                        ),
                    )

                tasks: list[asyncio.Task] = []
                credits_left = self._total_credits - self._sent_credits
                for _ in range(min(self._credits_available, credits_left)):
                    task = asyncio.create_task(drop_task())
                    self._sent_credits += 1
                    self._credits_available -= 1
                    tasks.append(task)

                await asyncio.gather(*tasks)

                if self._sent_credits >= self._total_credits:
                    self.logger.debug("All credits sent, stopping credit drop task")
                    break

            except asyncio.CancelledError:
                self.logger.debug("Credit drop task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Exception issuing credit drop: {e}")
                await asyncio.sleep(0.1)

    async def _on_credit_return(self, message: CreditReturnMessage) -> None:
        """Process a credit return message.

        Args:
            message: The credit return message received from the pull request
        """
        self.logger.debug(f"Processing credit return: {message}")
        async with self._credit_lock:
            self._credits_available += message.amount
            self._completed_credits += message.amount

        self.logger.debug(
            "Processing credit return: %s (completed credits: %s of %s) (%.2f requests/s)",
            message.amount,
            self._completed_credits,
            self._total_credits,
            self._completed_credits
            / (time.time_ns() - self.start_time_ns)
            * NANOS_PER_SECOND,
        )

        if self._completed_credits >= self._total_credits:
            self.logger.debug(
                "All credits completed, stopping credit drop task after %.2f seconds (%.2f requests/s)",
                (time.time_ns() - self.start_time_ns) / NANOS_PER_SECOND,
                self._total_credits
                / ((time.time_ns() - self.start_time_ns) / NANOS_PER_SECOND),
            )

            await self.pub_client.publish(
                CreditsCompleteMessage(
                    service_id=self.service_id, cancelled=self.stop_event.is_set()
                ),
            )

        self._credit_event.set()

    @aiperf_task
    async def _report_progress_task(self) -> None:
        """Report the progress."""
        while not self.stop_event.is_set():
            await self.pub_client.publish(
                ProfileProgressMessage(
                    service_id=self.service_id,
                    start_ns=self.start_time_ns,
                    total=self._total_credits,
                    completed=self._completed_credits,
                ),
            )
            await asyncio.sleep(1)


def main() -> None:
    """Main entry point for the timing manager."""
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(TimingManager)


if __name__ == "__main__":
    sys.exit(main())
