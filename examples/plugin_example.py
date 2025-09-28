#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Example demonstrating the modern AIPerf dependency injection system.

This example shows how to:
1. Use the modern factory system
2. Create custom plugins
3. Use dependency injection decorators
4. Validate protocol compliance
"""

from typing import Protocol, runtime_checkable
from enum import Enum

from aiperf.common.di_container import main_container, service_inject
from aiperf.common.modern_factories import service_factory
from aiperf.common.protocol_validation import validate_plugin, ValidatedProtocol
from aiperf.common.enums import ServiceType


@runtime_checkable
class ExampleProtocol(ValidatedProtocol):
    """Example protocol for demonstration."""

    def process_data(self, data: str) -> str:
        """Process some data."""
        ...

    def get_status(self) -> bool:
        """Get service status."""
        ...


class CustomService:
    """Example custom service implementation."""

    def __init__(self, name: str = "CustomService"):
        self.name = name
        self._running = False

    def process_data(self, data: str) -> str:
        """Process data with custom logic."""
        return f"[{self.name}] Processed: {data.upper()}"

    def get_status(self) -> bool:
        """Get service status."""
        return self._running

    def start(self) -> None:
        """Start the service."""
        self._running = True
        print(f"{self.name} started")

    def stop(self) -> None:
        """Stop the service."""
        self._running = False
        print(f"{self.name} stopped")


def example_basic_usage():
    """Example of basic factory usage."""
    print("=== Basic Factory Usage ===")

    try:
        # This will work if you have services registered via entry points
        service = service_factory.create_instance(
            ServiceType.SYSTEM_CONTROLLER,
            service_config=None,  # Would normally pass real config
            user_config=None      # Would normally pass real config
        )
        print(f"Created service: {type(service).__name__}")
    except Exception as e:
        print(f"Could not create service (expected in example): {e}")

    # List available services
    available = service_factory.get_available_implementations()
    print(f"Available services: {available}")


def example_plugin_validation():
    """Example of plugin validation."""
    print("\n=== Plugin Validation ===")

    # Create a custom service
    custom_service = CustomService("TestService")

    # Validate it implements our protocol
    is_valid = validate_plugin(custom_service, ExampleProtocol, "CustomService")
    print(f"CustomService implements ExampleProtocol: {is_valid}")

    # Use the service
    if is_valid:
        result = custom_service.process_data("hello world")
        print(f"Processing result: {result}")
        print(f"Service status: {custom_service.get_status()}")


@service_inject(service_factory, ServiceType.SYSTEM_CONTROLLER)
def example_dependency_injection(injected_service, user_data: str):
    """Example of dependency injection decorator."""
    print(f"\n=== Dependency Injection ===")
    print(f"Injected service type: {type(injected_service).__name__}")
    print(f"User data: {user_data}")
    return f"Processed {user_data} with {type(injected_service).__name__}"


def example_container_inspection():
    """Example of inspecting the DI container."""
    print("\n=== Container Inspection ===")

    # List all available plugins
    plugins = main_container.list_plugins()
    for plugin_type, plugin_list in plugins.items():
        print(f"{plugin_type}: {plugin_list}")


def example_error_handling():
    """Example of error handling."""
    print("\n=== Error Handling ===")

    try:
        # Try to create a non-existent service
        service = service_factory.create_instance("non_existent_service")
    except Exception as e:
        print(f"Expected error for non-existent service: {e}")

    try:
        # Try to get a plugin that doesn't exist
        provider = main_container.get_plugin_provider("services", "fake_service")
    except Exception as e:
        print(f"Expected error for fake service: {e}")


class AdvancedCustomService(CustomService):
    """Advanced custom service with additional features."""

    def __init__(self, name: str = "AdvancedService", config: dict = None):
        super().__init__(name)
        self.config = config or {}
        self.metrics = {"processed": 0, "errors": 0}

    def process_data(self, data: str) -> str:
        """Process data with metrics tracking."""
        try:
            result = super().process_data(data)
            self.metrics["processed"] += 1
            return result
        except Exception:
            self.metrics["errors"] += 1
            raise

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self.metrics.copy()


def example_advanced_features():
    """Example of advanced features."""
    print("\n=== Advanced Features ===")

    # Create advanced service with configuration
    config = {"max_items": 100, "timeout": 30}
    advanced_service = AdvancedCustomService("AdvancedService", config)

    # Process multiple items
    for i in range(3):
        result = advanced_service.process_data(f"item_{i}")
        print(f"Result {i}: {result}")

    # Check metrics
    metrics = advanced_service.get_metrics()
    print(f"Service metrics: {metrics}")


def main():
    """Run all examples."""
    print("AIPerf Modern Dependency Injection Examples")
    print("=" * 50)

    example_basic_usage()
    example_plugin_validation()

    # Note: This will fail unless services are properly registered
    try:
        example_dependency_injection("test data")
    except Exception as e:
        print(f"DI example failed (expected): {e}")

    example_container_inspection()
    example_error_handling()
    example_advanced_features()

    print("\n=== Migration Tips ===")
    print("1. Replace old factory imports with modern ones")
    print("2. Use entry points instead of @register decorators")
    print("3. Add protocol validation to your services")
    print("4. Use dependency injection for cleaner code")
    print("5. Leverage the plugin system for extensibility")


if __name__ == "__main__":
    main()
