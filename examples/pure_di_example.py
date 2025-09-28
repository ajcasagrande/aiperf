#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Example demonstrating pure dependency injection without any factory patterns.

This shows the clean, modern approach to service creation and management.
"""

from aiperf.di import (
    create_service,
    create_client,
    create_exporter,
    inject_service,
    auto_wire,
    list_services,
    app_container,
)
from aiperf.common.enums import ServiceType


def example_pure_service_creation():
    """Example of pure service creation without factories."""
    print("=== Pure Service Creation ===")

    try:
        # Create services directly - no factories needed
        system_controller = create_service(
            ServiceType.SYSTEM_CONTROLLER,
            service_config=None,  # Would be real config
            user_config=None      # Would be real config
        )
        print(f"Created: {type(system_controller).__name__}")

        # Create worker manager
        worker_manager = create_service(
            ServiceType.WORKER_MANAGER,
            service_config=None,
            user_config=None,
            worker_count=8
        )
        print(f"Created: {type(worker_manager).__name__}")

    except Exception as e:
        print(f"Service creation example (expected failure): {e}")


@inject_service(ServiceType.WORKER_MANAGER)
def example_automatic_injection(worker_service, task_data: str):
    """Example of automatic service injection."""
    print(f"\n=== Automatic Injection ===")
    print(f"Injected service: {type(worker_service).__name__}")
    print(f"Processing: {task_data}")
    return f"Processed {task_data} with {type(worker_service).__name__}"


@auto_wire(service_mapping={'controller': 'system_controller', 'manager': 'worker_manager'})
def example_auto_wiring(controller, manager, data: str):
    """Example of automatic dependency wiring."""
    print(f"\n=== Auto Wiring ===")
    print(f"Controller: {type(controller).__name__}")
    print(f"Manager: {type(manager).__name__}")
    return f"Auto-wired processing of {data}"


def example_container_usage():
    """Example of direct container usage."""
    print(f"\n=== Direct Container Usage ===")

    # List all available services
    services = app_container.list_available_services()
    for category, service_list in services.items():
        print(f"{category}: {service_list}")

    # Get service directly from container
    try:
        service = app_container.get_service("system_controller")
        print(f"Container service: {type(service).__name__}")
    except Exception as e:
        print(f"Container access (expected failure): {e}")


def example_configuration_driven():
    """Example of configuration-driven service creation."""
    print(f"\n=== Configuration-Driven Services ===")

    # Configure container from dictionary
    config = {
        'services': {
            'worker_manager': {
                'worker_count': 16,
                'max_queue_size': 1000
            }
        },
        'clients': {
            'http_client': {
                'timeout': 30,
                'max_retries': 3
            }
        }
    }

    app_container.configure_from_dict(config)
    print("Container configured with custom settings")

    try:
        # Services will now use configured parameters
        worker = create_service(ServiceType.WORKER_MANAGER)
        print(f"Configured worker: {type(worker).__name__}")
    except Exception as e:
        print(f"Configured service creation (expected failure): {e}")


def example_client_and_exporter_creation():
    """Example of creating clients and exporters."""
    print(f"\n=== Clients and Exporters ===")

    try:
        # Create HTTP client
        http_client = create_client("aiohttp_client", base_url="https://api.example.com")
        print(f"Created client: {type(http_client).__name__}")

        # Create JSON exporter
        json_exporter = create_exporter("json_exporter", output_file="results.json")
        print(f"Created exporter: {type(json_exporter).__name__}")

    except Exception as e:
        print(f"Client/Exporter creation (expected failure): {e}")


def example_service_lifecycle():
    """Example of service lifecycle management."""
    print(f"\n=== Service Lifecycle ===")

    try:
        # Create service
        service = create_service(
            ServiceType.DATASET_MANAGER,
            service_config=None,
            user_config=None
        )

        # Use service methods
        print(f"Service created: {type(service).__name__}")

        # Services are automatically managed by the DI container
        # No manual lifecycle management needed

    except Exception as e:
        print(f"Service lifecycle example (expected failure): {e}")


class CustomProcessor:
    """Example of a custom service that could be registered via entry points."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.processed_count = 0

    def process(self, data: list) -> list:
        """Process data in batches."""
        results = []
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            # Process batch
            results.extend([f"processed_{item}" for item in batch])
            self.processed_count += len(batch)
        return results


def example_plugin_style_usage():
    """Example showing how users would create plugins."""
    print(f"\n=== Plugin-Style Usage ===")

    # This shows how a user would create their own service
    processor = CustomProcessor(batch_size=50)

    # Process some data
    test_data = [f"item_{i}" for i in range(10)]
    results = processor.process(test_data)

    print(f"Processed {len(test_data)} items -> {len(results)} results")
    print(f"Processor stats: {processor.processed_count} total processed")

    # In real usage, this would be registered via entry points:
    # [project.entry-points."aiperf.processors"]
    # custom_processor = "my_package.processors:CustomProcessor"


def main():
    """Run all examples."""
    print("AIPerf Pure Dependency Injection Examples")
    print("=" * 50)

    example_pure_service_creation()

    # These will fail without proper service registration, but show the API
    try:
        example_automatic_injection("test data")
    except Exception as e:
        print(f"Injection example failed (expected): {e}")

    try:
        example_auto_wiring("test data")
    except Exception as e:
        print(f"Auto-wire example failed (expected): {e}")

    example_container_usage()
    example_configuration_driven()
    example_client_and_exporter_creation()
    example_service_lifecycle()
    example_plugin_style_usage()

    print(f"\n=== Key Benefits ===")
    print("✅ No factory classes or decorators needed")
    print("✅ Pure dependency injection with lazy loading")
    print("✅ Entry points for plugin registration")
    print("✅ Configuration-driven service creation")
    print("✅ Automatic dependency resolution")
    print("✅ Type-safe service interfaces")
    print("✅ Clean separation of concerns")


if __name__ == "__main__":
    main()
