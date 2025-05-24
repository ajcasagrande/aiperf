#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Demonstration of multiple mixins implementing the same protocol method.
"""

from typing import Protocol


class SupportsInitialize(Protocol):
    """Protocol for classes that support initialization."""

    def initialize(self) -> None:
        """Initialize the service."""
        ...


# Mixin 1 - Database initialization
class DatabaseMixin:
    """Mixin for database initialization."""

    def initialize(self) -> None:
        print("DatabaseMixin: Initializing database connection")
        # Call super() to ensure other mixins' initialize methods are called
        super().initialize()


# Mixin 2 - Logging initialization
class LoggingMixin:
    """Mixin for logging initialization."""

    def initialize(self) -> None:
        print("LoggingMixin: Setting up logging")
        # Call super() to ensure other mixins' initialize methods are called
        super().initialize()


# Base class
class BaseService:
    """Base service class."""

    def initialize(self) -> None:
        print("BaseService: Base initialization")


# Example 1: Without proper super() calls (BAD)
class BadDatabaseMixin:
    """Bad example - doesn't call super()."""

    def initialize(self) -> None:
        print("BadDatabaseMixin: Initializing database (no super call)")


class BadLoggingMixin:
    """Bad example - doesn't call super()."""

    def initialize(self) -> None:
        print("BadLoggingMixin: Setting up logging (no super call)")


# Service implementations
class GoodService(DatabaseMixin, LoggingMixin, BaseService):
    """Service with proper mixin usage."""

    pass


class BadService(BadDatabaseMixin, BadLoggingMixin, BaseService):
    """Service with improper mixin usage."""

    pass


class ServiceWithOwnInitialize(DatabaseMixin, LoggingMixin, BaseService):
    """Service that also has its own initialize method."""

    def initialize(self) -> None:
        print("ServiceWithOwnInitialize: Service-specific initialization")
        super().initialize()


def demonstrate_mro():
    """Demonstrate Method Resolution Order."""
    print("=== Method Resolution Order ===")
    print("GoodService MRO:", [cls.__name__ for cls in GoodService.__mro__])
    print("BadService MRO:", [cls.__name__ for cls in BadService.__mro__])
    print()


def demonstrate_good_mixins():
    """Demonstrate proper mixin usage with super() calls."""
    print("=== Good Mixins (with super() calls) ===")
    service = GoodService()
    service.initialize()
    print()


def demonstrate_bad_mixins():
    """Demonstrate improper mixin usage without super() calls."""
    print("=== Bad Mixins (without super() calls) ===")
    service = BadService()
    service.initialize()  # Only the first mixin's initialize will be called
    print()


def demonstrate_service_with_own_initialize():
    """Demonstrate service with its own initialize method."""
    print("=== Service with own initialize method ===")
    service = ServiceWithOwnInitialize()
    service.initialize()
    print()


if __name__ == "__main__":
    demonstrate_mro()
    demonstrate_good_mixins()
    demonstrate_bad_mixins()
    demonstrate_service_with_own_initialize()
