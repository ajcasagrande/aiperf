# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.enums import CreditPhase
from aiperf.common.messages import (
    CreditDropMessage,
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditReturnMessage,
)
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import CreditIssuingStrategy


class MockCreditManager(AIPerfLoggerMixin):
    """Mock implementation of CreditManagerProtocol for testing."""

    def __init__(self):
        self.dropped_credits = []
        self.progress_calls = []
        self.credits_complete_calls = []
        self.credit_strategy: CreditIssuingStrategy | None = None
        self.auto_credit_return = False

    async def drop_credit(
        self,
        credit_phase: CreditPhase,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None:
        """Mock drop_credit method."""
        self.dropped_credits.append(
            CreditDropMessage(
                service_id="test-service",
                phase=credit_phase,
                conversation_id=conversation_id,
                credit_drop_ns=credit_drop_ns,
            )
        )
        if not self.auto_credit_return:
            return

        if self.credit_strategy is None:
            self.logger.warning("Credit strategy not set, skipping credit return")
            return

        await self.credit_strategy._on_credit_return(
            CreditReturnMessage(
                service_id="test-service",
                phase=credit_phase,
            )
        )

    async def publish_progress(
        self,
        credit_phase: CreditPhase,
        sent: int,
        completed: int,
    ) -> None:
        """Mock publish_progress method."""
        self.progress_calls.append(
            CreditPhaseProgressMessage(
                phase=credit_phase,
                sent=sent,
                completed=completed,
                service_id="test-service",
            )
        )

    async def publish_credits_complete(
        self, credit_phase: CreditPhase, completed: int
    ) -> None:
        """Mock publish_credits_complete method."""
        self.credits_complete_calls.append(
            CreditPhaseCompleteMessage(
                phase=credit_phase,
                completed=completed,
                service_id="test-service",
            )
        )


@pytest.fixture
def mock_credit_manager():
    """Fixture providing a mock credit manager."""
    return MockCreditManager()


@pytest.fixture
def config():
    """Fixture providing a TimingManagerConfig instance."""
    return TimingManagerConfig()
