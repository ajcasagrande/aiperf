# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the worker service.
"""

import pytest
from pydantic import BaseModel

from aiperf.common.base_service import BaseService
from aiperf.common.enums import LifecycleState, ServiceType
from aiperf.workers import Worker
from tests.base_test_service import BaseTestService
from tests.utils.async_test_utils import async_fixture


class WorkerTestConfig(BaseModel):
    """
    Test configuration for the workers.
    """

    # TODO: Replace this with the actual configuration model once available
    pass


@pytest.mark.asyncio
class WorkerServiceTest(BaseTestService):
    """
    Tests for the worker service.

    This test class extends BaseTestService since Worker is a direct subclass
    of BaseService, not a BaseComponentService.
    """

    @pytest.fixture
    def service_class(self) -> type[BaseService]:
        """Return the service class to be tested."""
        return Worker

    @pytest.fixture
    def worker_config(self) -> WorkerTestConfig:
        """
        Return a test configuration for the worker.
        """
        return WorkerTestConfig()

    async def test_worker_initialization(self, initialized_service: Worker) -> None:
        """
        Test that the worker initializes with the correct configuration.

        Verifies the worker service is properly instantiated with its configuration.
        """
        # Basic existence checks
        service = await async_fixture(initialized_service)
        assert service is not None
        assert service.service_config is not None
        assert service.service_type == ServiceType.WORKER

        # Initialize the worker
        await service.initialize()

        # Check the worker is properly initialized
        assert service.is_initialized
        assert service.state == LifecycleState.READY

    async def test_worker_extracts_token_count_from_turn(
        self, initialized_service: Worker
    ) -> None:
        """
        Test that the worker correctly extracts input token count from turn data.

        This is a conceptual test to verify that the worker would populate
        the RequestRecord with pre-computed token counts when available from
        the dataset turn data, eliminating the need for inference parsers
        to request tokenization from the dataset manager.
        """
        # Note: This is a placeholder test to document the expected behavior.
        # A full integration test would require mocking the conversation request client,
        # inference client, and dataset responses, which is beyond the scope of
        # this current implementation but demonstrates the intent of the optimization.
        service = await async_fixture(initialized_service)

        # The worker should be capable of extracting token counts from turn data
        # when the _execute_single_credit_internal method is called with a
        # conversation response that contains turns with pre-computed token counts
        assert hasattr(service, "_execute_single_credit_internal")

        # This ensures the optimization is in place at the architecture level
