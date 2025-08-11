# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Example tests demonstrating how to use the BaseTestService classes.
"""

import pytest

from tests.common.conftest import BaseTestService, BaseTestServiceWithMixins


class TestExampleBaseService(BaseTestService):
    """Example test class showing how to use BaseTestService."""

    def test_service_creation(self, base_test_service):
        """Test that a basic service can be created with all dependencies mocked."""
        service = base_test_service

        # Use the helper assertion methods
        self.assert_service_initialized(service)
        self.assert_communication_setup(service)

        # Test service-specific functionality
        assert service.service_type is not None
        assert service._mock_communication_factory is not None

    def test_service_configuration(self, base_test_service):
        """Test that service configuration is properly set up."""
        service = base_test_service

        assert service.service_config.service_run_type is not None
        assert service.service_config.comm_backend is not None
        assert service.user_config.endpoint is not None


class TestExampleServiceWithMixins(BaseTestServiceWithMixins):
    """Example test class showing how to use BaseTestServiceWithMixins."""

    def test_service_with_pull_client(self, test_service_with_pull_client):
        """Test a service that includes PullClientMixin."""
        service = test_service_with_pull_client

        # Use base assertions
        self.assert_service_initialized(service)
        self.assert_communication_setup(service)

        # Use mixin-specific assertions
        self.assert_pull_client_setup(service)

    def test_service_with_reply_client(self, test_service_with_reply_client):
        """Test a service that includes ReplyClientMixin."""
        service = test_service_with_reply_client

        self.assert_service_initialized(service)
        self.assert_communication_setup(service)
        self.assert_reply_client_setup(service)

    def test_service_with_process_health(self, test_service_with_process_health):
        """Test a service that includes ProcessHealthMixin."""
        service = test_service_with_process_health

        self.assert_service_initialized(service)
        self.assert_communication_setup(service)
        self.assert_process_health_setup(service)


class TestCustomServiceExample(BaseTestServiceWithMixins):
    """Example showing how to create custom service tests."""

    @pytest.fixture
    def custom_test_service(
        self,
        mock_service_config,
        mock_user_config,
        mock_service_id,
        mock_communication_factory,
    ):
        """Create a custom service for testing specific functionality."""
        from aiperf.common.base_service import BaseService
        from aiperf.common.enums import CommAddress, ServiceType
        from aiperf.common.mixins import ProcessHealthMixin, PullClientMixin

        class CustomTestService(ProcessHealthMixin, PullClientMixin, BaseService):
            service_type = ServiceType.DATASET_MANAGER

            def handle_command(self, command):
                return f"Handled command: {command}"

            def custom_method(self):
                return "custom_result"

        return CustomTestService(
            service_config=mock_service_config,
            user_config=mock_user_config,
            service_id=mock_service_id,
            pull_client_address=CommAddress.EVENT_BUS_PROXY_FRONTEND,
        )

    def test_custom_service_functionality(self, custom_test_service):
        """Test custom service methods."""
        service = custom_test_service

        # Test that all mixins are properly set up
        self.assert_service_initialized(service)
        self.assert_communication_setup(service)
        self.assert_process_health_setup(service)
        self.assert_pull_client_setup(service)

        # Test custom functionality
        result = service.custom_method()
        assert result == "custom_result"

        # Test command handling
        command_result = service.handle_command("test_command")
        assert command_result == "Handled command: test_command"
