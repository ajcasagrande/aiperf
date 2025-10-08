# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.enums import CommandType, ServiceRegistrationStatus, ServiceType
from aiperf.common.exceptions import LifecycleOperationError
from aiperf.common.messages.command_messages import CommandErrorResponse
from aiperf.common.models import ErrorDetails, ExitErrorInfo
from aiperf.controller.system_controller import SystemController
from tests.controller.conftest import MockTestException


def assert_exit_error(
    system_controller: SystemController,
    expected_error_or_exception: ErrorDetails | LifecycleOperationError,
    operation: str,
    service_id: str | None,
) -> None:
    """Assert that an exit error was recorded with the proper details."""
    assert len(system_controller._exit_errors) == 1
    exit_error = system_controller._exit_errors[0]
    assert isinstance(exit_error, ExitErrorInfo)

    # Handle both ErrorDetails objects and LifecycleOperationError objects
    if isinstance(expected_error_or_exception, ErrorDetails):
        expected_error_details = expected_error_or_exception
    else:
        expected_error_details = ErrorDetails.from_exception(
            expected_error_or_exception
        )

    assert exit_error.error_details == expected_error_details
    assert exit_error.operation == operation
    assert exit_error.service_id == service_id


class TestSystemController:
    """Test SystemController."""

    @pytest.mark.asyncio
    async def test_system_controller_no_error_on_initialize_success(
        self, system_controller: SystemController, mock_service_manager: AsyncMock
    ):
        """Test that SystemController does not exit when initialize succeeds."""
        mock_service_manager.initialize.return_value = None
        await system_controller._initialize_system_controller()
        # Verify that no exit errors were recorded
        assert len(system_controller._exit_errors) == 0

    @pytest.mark.asyncio
    async def test_system_controller_no_error_on_start_success(
        self, system_controller: SystemController, mock_service_manager: AsyncMock
    ):
        """Test that SystemController does not exit when start services succeeds."""
        mock_service_manager.start.return_value = None
        mock_service_manager.wait_for_all_services_registration.return_value = None
        system_controller._start_profiling_all_services = AsyncMock(return_value=None)
        system_controller._profile_configure_all_services = AsyncMock(return_value=None)

        await system_controller._start_services()
        # Verify that no exit errors were recorded
        assert len(system_controller._exit_errors) == 0

        assert mock_service_manager.start.called
        assert mock_service_manager.wait_for_all_services_registration.called
        assert system_controller._start_profiling_all_services.called
        assert system_controller._profile_configure_all_services.called


class TestSystemControllerExitScenarios:
    """Test exit scenarios for the SystemController."""

    @pytest.mark.asyncio
    async def test_system_controller_exits_on_profile_configure_error_response(
        self,
        system_controller: SystemController,
        mock_exception: MockTestException,
        error_response: CommandErrorResponse,
    ):
        """Test that SystemController exits when receiving a CommandErrorResponse for profile_configure."""
        error_responses = [
            error_response.model_copy(
                deep=True, update={"command": CommandType.PROFILE_CONFIGURE}
            )
        ]
        # Mock the command responses
        system_controller.send_command_and_wait_for_all_responses = AsyncMock(
            return_value=error_responses
        )

        with pytest.raises(
            LifecycleOperationError,
            match="Failed to perform operation 'Configure Profiling'",
        ):
            await system_controller._profile_configure_all_services()

        # Verify that exit errors were recorded
        assert_exit_error(
            system_controller,
            error_response.error,
            "Configure Profiling",
            error_responses[0].service_id,
        )

    @pytest.mark.asyncio
    async def test_system_controller_exits_on_profile_start_error_response(
        self,
        system_controller: SystemController,
        mock_exception: MockTestException,
        error_response: CommandErrorResponse,
    ):
        """Test that SystemController exits when receiving a CommandErrorResponse for profile_start."""
        error_responses = [
            error_response.model_copy(
                deep=True, update={"command": CommandType.PROFILE_START}
            )
        ]
        # Mock the command responses
        system_controller.send_command_and_wait_for_all_responses = AsyncMock(
            return_value=error_responses
        )

        with pytest.raises(
            LifecycleOperationError,
            match="Failed to perform operation 'Start Profiling'",
        ):
            await system_controller._start_profiling_all_services()

        # Verify that exit errors were recorded
        assert_exit_error(
            system_controller,
            error_response.error,
            "Start Profiling",
            error_responses[0].service_id,
        )

    @pytest.mark.asyncio
    async def test_system_controller_exits_on_service_manager_initialize_error(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
        mock_exception: MockTestException,
    ):
        """Test that SystemController exits when the service manager initialize fails."""
        mock_service_manager.initialize.side_effect = mock_exception
        with pytest.raises(LifecycleOperationError, match=str(mock_exception)):
            await system_controller._initialize_system_controller()

        # Verify that exit errors were recorded
        assert_exit_error(
            system_controller,
            mock_exception,
            "Initialize Service Manager",
            system_controller.id,
        )

    @pytest.mark.asyncio
    async def test_system_controller_exits_on_service_manager_start_error(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
        mock_exception: MockTestException,
    ):
        """Test that SystemController exits when the service manager start fails."""
        mock_service_manager.start.side_effect = LifecycleOperationError(
            operation="Start Service",
            original_exception=mock_exception,
            lifecycle_id=system_controller.id,
        )
        with pytest.raises(LifecycleOperationError, match="Test error"):
            await system_controller._start_services()

        # Verify that exit errors were recorded
        assert_exit_error(
            system_controller,
            LifecycleOperationError(
                operation="Start Service",
                original_exception=mock_exception,
                lifecycle_id=system_controller.id,
            ),
            "Start Service Manager",
            system_controller.id,
        )

    @pytest.mark.asyncio
    async def test_system_controller_exits_on_wait_for_all_services_registration_error(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
        mock_exception: MockTestException,
    ):
        """Test that SystemController exits when the service manager wait_for_all_services_registration fails."""
        mock_service_manager.start.return_value = None
        mock_service_manager.wait_for_all_services_registration.side_effect = (
            LifecycleOperationError(
                operation="Register Service",
                original_exception=mock_exception,
                lifecycle_id=system_controller.id,
            )
        )
        with pytest.raises(LifecycleOperationError, match="Test error"):
            await system_controller._start_services()

        # Verify that exit errors were recorded
        assert_exit_error(
            system_controller,
            LifecycleOperationError(
                operation="Register Service",
                original_exception=mock_exception,
                lifecycle_id=system_controller.id,
            ),
            "Register Services",
            system_controller.id,
        )


class TestServiceFailedMessageHandler:
    """Test ServiceFailedMessage handling in SystemController."""

    @pytest.mark.asyncio
    async def test_required_service_failure_triggers_shutdown(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test that a required service failure triggers system shutdown."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add a required service to the service manager
        required_service = ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            service_id="dataset_manager_123",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=True,
        )
        mock_service_manager.service_id_map["dataset_manager_123"] = required_service
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = (
            lambda sid: sid == "dataset_manager_123"
        )

        # Create a service failed message
        failed_message = ServiceFailedMessage(
            service_id="dataset_manager_123",
            error=ErrorDetails(message="Service crashed unexpectedly"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        # Process the message
        await system_controller._process_service_failed_message(failed_message)

        # Verify that exit errors were recorded
        assert len(system_controller._exit_errors) == 1
        exit_error = system_controller._exit_errors[0]
        assert exit_error.service_id == "dataset_manager_123"
        assert exit_error.operation == "Service Failure"
        assert "crashed unexpectedly" in exit_error.error_details.message

        # Verify that stop was called
        system_controller.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_required_service_failure_does_not_trigger_shutdown(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test that a non-required service failure does NOT trigger shutdown."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add a non-required service to the service manager
        optional_service = ServiceRunInfo(
            service_type=ServiceType.WORKER,
            service_id="worker_456",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=False,
        )
        mock_service_manager.service_id_map["worker_456"] = optional_service
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = lambda sid: False

        # Create a service failed message
        failed_message = ServiceFailedMessage(
            service_id="worker_456",
            error=ErrorDetails(message="Worker exited"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        # Process the message
        await system_controller._process_service_failed_message(failed_message)

        # Verify that NO exit errors were recorded
        assert len(system_controller._exit_errors) == 0

        # Verify that stop was NOT called
        system_controller.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_required_service_failures(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test handling of multiple required service failures."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add required services
        required_services = {
            "dataset_manager_1": ServiceType.DATASET_MANAGER,
            "timing_manager_1": ServiceType.TIMING_MANAGER,
        }

        for service_id, service_type in required_services.items():
            service_info = ServiceRunInfo(
                service_type=service_type,
                service_id=service_id,
                registration_status=ServiceRegistrationStatus.REGISTERED,
                required=True,
            )
            mock_service_manager.service_id_map[service_id] = service_info

        mock_service_manager.required_services = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
        }
        mock_service_manager.is_required_service = lambda sid: sid in required_services

        # Process first failure
        failed_message_1 = ServiceFailedMessage(
            service_id="dataset_manager_1",
            error=ErrorDetails(message="Dataset manager crashed"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )
        await system_controller._process_service_failed_message(failed_message_1)

        # Process second failure
        failed_message_2 = ServiceFailedMessage(
            service_id="timing_manager_1",
            error=ErrorDetails(message="Timing manager crashed"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )
        await system_controller._process_service_failed_message(failed_message_2)

        # Verify that both exit errors were recorded
        assert len(system_controller._exit_errors) == 2
        assert system_controller._exit_errors[0].service_id == "dataset_manager_1"
        assert system_controller._exit_errors[1].service_id == "timing_manager_1"

        # Stop should have been called twice (once per failure)
        assert system_controller.stop.call_count == 2

    @pytest.mark.asyncio
    async def test_service_failed_message_with_detailed_error(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test ServiceFailedMessage with detailed error information."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add a required service
        service_info = ServiceRunInfo(
            service_type=ServiceType.RECORDS_MANAGER,
            service_id="records_manager_999",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=True,
        )
        mock_service_manager.service_id_map["records_manager_999"] = service_info
        mock_service_manager.required_services = {ServiceType.RECORDS_MANAGER: 1}
        mock_service_manager.is_required_service = (
            lambda sid: sid == "records_manager_999"
        )

        # Create detailed error
        detailed_error = ErrorDetails(
            message="Critical error in records processing",
            type="RecordsProcessingException",
            code=500,
        )

        failed_message = ServiceFailedMessage(
            service_id="records_manager_999",
            error=detailed_error,
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        await system_controller._process_service_failed_message(failed_message)

        # Verify detailed error was preserved
        exit_error = system_controller._exit_errors[0]
        assert exit_error.error_details.type == "RecordsProcessingException"
        assert exit_error.error_details.code == 500
        assert "Critical error" in exit_error.error_details.message

    @pytest.mark.asyncio
    async def test_service_failed_message_unknown_service(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test ServiceFailedMessage for a service not in the service map."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails

        # Service not in the map
        mock_service_manager.service_id_map = {}
        mock_service_manager.is_required_service = lambda sid: False

        failed_message = ServiceFailedMessage(
            service_id="unknown_service_xyz",
            error=ErrorDetails(message="Unknown service failed"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        await system_controller._process_service_failed_message(failed_message)

        # Should not crash, and should treat as non-required
        assert len(system_controller._exit_errors) == 0
        system_controller.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_failed_message_with_empty_error(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test ServiceFailedMessage with minimal error information."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        service_info = ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            service_id="dataset_manager_min",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=True,
        )
        mock_service_manager.service_id_map["dataset_manager_min"] = service_info
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = (
            lambda sid: sid == "dataset_manager_min"
        )

        # Error with minimal information
        minimal_error = ErrorDetails(message="")

        failed_message = ServiceFailedMessage(
            service_id="dataset_manager_min",
            error=minimal_error,
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        await system_controller._process_service_failed_message(failed_message)

        # Should still record the error
        assert len(system_controller._exit_errors) == 1
        system_controller.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_failed_message_race_condition_with_shutdown(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test ServiceFailedMessage handling during shutdown."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Simulate system already shutting down
        system_controller.stop_requested = True

        service_info = ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            service_id="dataset_manager_race",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=True,
        )
        mock_service_manager.service_id_map["dataset_manager_race"] = service_info
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = lambda sid: True

        failed_message = ServiceFailedMessage(
            service_id="dataset_manager_race",
            error=ErrorDetails(message="Service failed during shutdown"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        await system_controller._process_service_failed_message(failed_message)

        # Should still record error even during shutdown
        assert len(system_controller._exit_errors) == 1

    @pytest.mark.asyncio
    async def test_mixed_required_and_optional_service_failures(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test handling mix of required and optional service failures."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add one required and one optional service
        required_service = ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            service_id="dataset_manager_req",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=True,
        )
        optional_service = ServiceRunInfo(
            service_type=ServiceType.WORKER,
            service_id="worker_opt",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=False,
        )
        mock_service_manager.service_id_map["dataset_manager_req"] = required_service
        mock_service_manager.service_id_map["worker_opt"] = optional_service
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = (
            lambda sid: sid == "dataset_manager_req"
        )

        # Optional service fails first
        optional_failed = ServiceFailedMessage(
            service_id="worker_opt",
            error=ErrorDetails(message="Worker died"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )
        await system_controller._process_service_failed_message(optional_failed)

        # Should not trigger shutdown
        assert len(system_controller._exit_errors) == 0
        system_controller.stop.assert_not_called()

        # Required service fails second
        required_failed = ServiceFailedMessage(
            service_id="dataset_manager_req",
            error=ErrorDetails(message="Dataset manager crashed"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )
        await system_controller._process_service_failed_message(required_failed)

        # Should trigger shutdown only for required service
        assert len(system_controller._exit_errors) == 1
        assert system_controller._exit_errors[0].service_id == "dataset_manager_req"
        system_controller.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_failed_message_removes_from_service_maps(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test that ServiceFailedMessage handler removes service from service maps."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add a required service
        service_info = ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            service_id="dataset_manager_cleanup",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=True,
        )
        mock_service_manager.service_id_map["dataset_manager_cleanup"] = service_info
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = (
            lambda sid: sid == "dataset_manager_cleanup"
        )
        mock_service_manager.remove_service_from_maps = MagicMock()

        failed_message = ServiceFailedMessage(
            service_id="dataset_manager_cleanup",
            error=ErrorDetails(message="Service crashed"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        await system_controller._process_service_failed_message(failed_message)

        # Verify remove_service_from_maps was called
        mock_service_manager.remove_service_from_maps.assert_called_once_with(
            "dataset_manager_cleanup"
        )

    @pytest.mark.asyncio
    async def test_service_failed_message_removes_optional_service_from_maps(
        self,
        system_controller: SystemController,
        mock_service_manager: AsyncMock,
    ):
        """Test that non-required services are also removed from maps."""
        from aiperf.common.messages import ServiceFailedMessage
        from aiperf.common.models import ErrorDetails
        from aiperf.common.models.service_models import ServiceRunInfo

        # Add a non-required service
        service_info = ServiceRunInfo(
            service_type=ServiceType.WORKER,
            service_id="worker_cleanup",
            registration_status=ServiceRegistrationStatus.REGISTERED,
            required=False,
        )
        mock_service_manager.service_id_map["worker_cleanup"] = service_info
        mock_service_manager.required_services = {ServiceType.DATASET_MANAGER: 1}
        mock_service_manager.is_required_service = lambda sid: False
        mock_service_manager.remove_service_from_maps = MagicMock()

        failed_message = ServiceFailedMessage(
            service_id="worker_cleanup",
            error=ErrorDetails(message="Worker exited"),
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )

        await system_controller._process_service_failed_message(failed_message)

        # Verify remove_service_from_maps was called even for optional service
        mock_service_manager.remove_service_from_maps.assert_called_once_with(
            "worker_cleanup"
        )
        # Should not trigger shutdown
        system_controller.stop.assert_not_called()
