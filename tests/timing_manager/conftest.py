# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

import pytest

from aiperf.common.enums import CreditPhase
from aiperf.common.models import CreditPhaseStats, CreditReturnMessage
from aiperf.services.timing_manager.config import TimingManagerConfig
from aiperf.services.timing_manager.credit_issuing_strategy import CreditIssuingStrategy


class MockCreditManager:
    """Mock implementation of CreditManagerProtocol for testing."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dropped_credits = []
        self.progress_calls = []
        self.credits_complete_calls = []
        self.credit_strategy: CreditIssuingStrategy | None = None
        self.auto_credit_return = False

    async def drop_credit(
        self,
        phase_type: CreditPhase,
        conversation_id: str | None = None,
        credit_drop_ns: int | None = None,
    ) -> None:
        """Mock drop_credit method."""
        self.dropped_credits.append(
            {
                "phase_type": phase_type,
                "conversation_id": conversation_id,
                "credit_drop_ns": credit_drop_ns,
            }
        )
        if not self.auto_credit_return:
            return

        if self.credit_strategy is None:
            self.logger.warning("Credit strategy not set, skipping credit return")
            return

        await self.credit_strategy._on_credit_return(
            CreditReturnMessage(
                service_id="test-service",
                conversation_id=conversation_id,
                credit_drop_ns=credit_drop_ns,
                delayed_ns=None,
            )
        )

    async def publish_progress(
        self,
        phase_stats: dict[CreditPhase, CreditPhaseStats],
    ) -> None:
        """Mock publish_progress method."""
        self.progress_calls.append(
            {
                "phase_stats": phase_stats,
            }
        )

    async def publish_credits_complete(
        self, phase_type: CreditPhase, cancelled: bool = False
    ) -> None:
        """Mock publish_credits_complete method."""
        self.credits_complete_calls.append(
            {"phase_type": phase_type, "cancelled": cancelled}
        )


@pytest.fixture
def mock_credit_manager():
    """Fixture providing a mock credit manager."""
    return MockCreditManager()


@pytest.fixture
def config():
    """Fixture providing a TimingManagerConfig instance."""
    return TimingManagerConfig()
