# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from unittest.mock import Mock

import pytest

from aiperf.common.enums import LifecycleState, ServiceRegistrationStatus, ServiceType
from aiperf.common.models.service_models import ServiceRunInfo
from aiperf.common.service_registry import ServiceRegistry


@pytest.fixture
def registry():
    """Create a ServiceRegistry instance for testing."""
    return ServiceRegistry(service_config=Mock(), user_config=Mock())


@pytest.fixture
def sample_service():
    """Create a sample ServiceRunInfo for testing."""
    return ServiceRunInfo(
        service_type=ServiceType.WORKER,
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_id="worker_test_001",
        state=LifecycleState.RUNNING,
    )


@pytest.mark.asyncio
async def test_expect_services(registry):
    """Test setting expected services by type."""
    expected = {ServiceType.WORKER: 2, ServiceType.DATASET_MANAGER: 1}
    await registry.expect_services(expected)
    assert registry.expected_by_type == expected


@pytest.mark.asyncio
async def test_expect_ids(registry):
    """Test setting expected service IDs."""
    service_ids = ["worker_001", "worker_002"]
    await registry.expect_ids(service_ids)
    assert registry.expected_ids == set(service_ids)


@pytest.mark.asyncio
async def test_register_service(registry, sample_service):
    """Test registering a service."""
    await registry.register(sample_service)

    assert sample_service.service_id in registry.services
    assert registry.services[sample_service.service_id] == sample_service
    assert sample_service.service_id in registry.by_type[sample_service.service_type]


@pytest.mark.asyncio
async def test_unregister_service(registry, sample_service):
    """Test unregistering a service."""
    await registry.register(sample_service)
    await registry.unregister(sample_service.service_id)

    assert sample_service.service_id not in registry.services
    assert sample_service not in registry.by_type.get(sample_service.service_type, [])


@pytest.mark.asyncio
async def test_wait_for_all_immediate(registry):
    """Test wait_for_all when services are already registered."""
    await registry.expect_services({ServiceType.WORKER: 1})

    service = ServiceRunInfo(
        service_type=ServiceType.WORKER,
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_id="worker_001",
        state=LifecycleState.RUNNING,
    )
    await registry.register(service)

    # Should return immediately since service is already registered
    await registry.wait_for_all()


@pytest.mark.asyncio
async def test_wait_for_all_async(registry):
    """Test wait_for_all when services register later."""
    await registry.expect_services({ServiceType.WORKER: 1})

    # Start waiting in background
    wait_task = asyncio.create_task(registry.wait_for_all())

    # Give the wait task a chance to start
    await asyncio.sleep(0.01)
    assert not wait_task.done()

    # Register the service
    service = ServiceRunInfo(
        service_type=ServiceType.WORKER,
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_id="worker_001",
        state=LifecycleState.RUNNING,
    )
    await registry.register(service)

    # Wait should complete
    await wait_task


@pytest.mark.asyncio
async def test_wait_for_type(registry):
    """Test wait_for_type functionality."""
    await registry.expect_services({ServiceType.WORKER: 2})

    # Start waiting in background
    wait_task = asyncio.create_task(registry.wait_for_type(ServiceType.WORKER))
    await asyncio.sleep(0.01)
    assert not wait_task.done()

    # Register first worker
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )
    await asyncio.sleep(0.01)
    assert not wait_task.done()  # Still need one more

    # Register second worker
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_002",
            state=LifecycleState.RUNNING,
        )
    )

    # Wait should complete
    await wait_task


@pytest.mark.asyncio
async def test_wait_for_ids(registry):
    """Test wait_for_ids functionality."""
    service_ids = ["worker_001", "manager_001"]

    # Start waiting in background
    wait_task = asyncio.create_task(registry.wait_for_ids(service_ids))
    await asyncio.sleep(0.01)
    assert not wait_task.done()

    # Register first service
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )
    await asyncio.sleep(0.01)
    assert not wait_task.done()  # Still need one more

    # Register second service
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="manager_001",
            state=LifecycleState.RUNNING,
        )
    )

    # Wait should complete
    await wait_task


@pytest.mark.asyncio
async def test_wait_for_type_immediate(registry):
    """Test wait_for_type when condition is already met."""
    await registry.expect_services({ServiceType.WORKER: 1})

    # Register service first
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )

    # Should return immediately
    await registry.wait_for_type(ServiceType.WORKER)


@pytest.mark.asyncio
async def test_all_registered(registry):
    """Test all_registered method."""
    await registry.expect_services({ServiceType.WORKER: 2})

    # Test service type completion
    assert not registry.all_registered(service_type=ServiceType.WORKER)

    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )
    assert not registry.all_registered(service_type=ServiceType.WORKER)

    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_002",
            state=LifecycleState.RUNNING,
        )
    )
    assert registry.all_registered(service_type=ServiceType.WORKER)

    # Test all services completion
    assert registry.all_registered()


@pytest.mark.asyncio
async def test_all_registered_service_ids(registry):
    """Test all_registered with specific service IDs."""
    service_ids = ["worker_001", "manager_001"]

    assert not registry.all_registered(service_ids=service_ids)

    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )
    assert not registry.all_registered(service_ids=service_ids)

    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="manager_001",
            state=LifecycleState.RUNNING,
        )
    )
    assert registry.all_registered(service_ids=service_ids)


@pytest.mark.asyncio
async def test_all_registered_invalid_args(registry):
    """Test all_registered with invalid argument combinations."""
    with pytest.raises(ValueError, match="Specify either service_type or service_ids"):
        registry.all_registered(
            service_type=ServiceType.WORKER, service_ids=["worker_001"]
        )


@pytest.mark.asyncio
async def test_get_services(registry):
    """Test get_services method."""
    worker1 = ServiceRunInfo(
        service_type=ServiceType.WORKER,
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_id="worker_001",
        state=LifecycleState.RUNNING,
    )
    worker2 = ServiceRunInfo(
        service_type=ServiceType.WORKER,
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_id="worker_002",
        state=LifecycleState.RUNNING,
    )
    manager = ServiceRunInfo(
        service_type=ServiceType.DATASET_MANAGER,
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_id="manager_001",
        state=LifecycleState.RUNNING,
    )

    await registry.register(worker1)
    await registry.register(worker2)
    await registry.register(manager)

    # Get by type
    workers = registry.get_services(ServiceType.WORKER)
    assert len(workers) == 2
    assert worker1 in workers
    assert worker2 in workers

    # Get all services
    all_services = registry.get_services()
    assert len(all_services) == 3
    assert worker1.service_id in all_services
    assert worker2.service_id in all_services
    assert manager.service_id in all_services


@pytest.mark.asyncio
async def test_get_service(registry, sample_service):
    """Test get_service method."""
    await registry.register(sample_service)

    retrieved = registry.get_service(sample_service.service_id)
    assert retrieved == sample_service

    assert registry.get_service("nonexistent") is None


@pytest.mark.asyncio
async def test_multiple_waiters(registry):
    """Test multiple concurrent waiters for the same condition."""
    await registry.expect_services({ServiceType.WORKER: 1})

    # Start multiple wait tasks
    wait_task1 = asyncio.create_task(registry.wait_for_type(ServiceType.WORKER))
    wait_task2 = asyncio.create_task(registry.wait_for_type(ServiceType.WORKER))
    wait_task3 = asyncio.create_task(registry.wait_for_all())

    await asyncio.sleep(0.01)
    assert not wait_task1.done()
    assert not wait_task2.done()
    assert not wait_task3.done()

    # Register the service
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )

    # All waiters should complete
    await wait_task1
    await wait_task2
    await wait_task3


@pytest.mark.asyncio
async def test_complex_scenario(registry):
    """Test a complex scenario with multiple service types and IDs."""
    # Set up expectations
    await registry.expect_services(
        {
            ServiceType.WORKER: 2,
            ServiceType.DATASET_MANAGER: 1,
        }
    )
    await registry.expect_ids(["special_service_001"])

    # Start various wait tasks
    wait_all_task = asyncio.create_task(registry.wait_for_all())
    wait_workers_task = asyncio.create_task(registry.wait_for_type(ServiceType.WORKER))
    wait_manager_task = asyncio.create_task(
        registry.wait_for_type(ServiceType.DATASET_MANAGER)
    )
    wait_special_task = asyncio.create_task(
        registry.wait_for_ids(["special_service_001"])
    )

    await asyncio.sleep(0.01)
    assert not any(
        task.done()
        for task in [
            wait_all_task,
            wait_workers_task,
            wait_manager_task,
            wait_special_task,
        ]
    )

    # Register first worker
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_001",
            state=LifecycleState.RUNNING,
        )
    )
    await asyncio.sleep(0.01)
    assert not any(
        task.done()
        for task in [
            wait_all_task,
            wait_workers_task,
            wait_manager_task,
            wait_special_task,
        ]
    )

    # Register second worker
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.WORKER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="worker_002",
            state=LifecycleState.RUNNING,
        )
    )
    await asyncio.sleep(0.01)
    assert wait_workers_task.done()  # Workers complete
    assert not any(
        task.done() for task in [wait_all_task, wait_manager_task, wait_special_task]
    )

    # Register dataset manager
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.DATASET_MANAGER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="dataset_manager_001",
            state=LifecycleState.RUNNING,
        )
    )
    await asyncio.sleep(0.01)
    assert wait_manager_task.done()  # Manager complete
    assert not any(task.done() for task in [wait_all_task, wait_special_task])

    # Register special service
    await registry.register(
        ServiceRunInfo(
            service_type=ServiceType.TIMING_MANAGER,
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_id="special_service_001",
            state=LifecycleState.RUNNING,
        )
    )

    # All should be complete now
    await wait_all_task
    await wait_special_task
