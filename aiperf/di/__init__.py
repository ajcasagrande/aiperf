# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Modern dependency injection system for AIPerf.

This package provides a complete dependency injection solution built on dependency-injector
with lazy loading, entry points discovery, and full type safety.
"""

from .containers import (
    ApplicationContainer,
    ServiceContainer,
    ClientContainer,
    ExporterContainer,
    ProcessorContainer,
    app_container,
    get_app_container,
)
from .providers import (
    LazyEntryPointProvider,
    ValidatedProvider,
    ConfigurableProvider,
)
from .decorators import (
    inject_service,
    inject_client,
    inject_exporter,
    auto_wire,
)
from .discovery import (
    discover_plugins,
    register_plugin,
    list_plugins,
)
from .services import (
    create_service,
    create_client,
    create_exporter,
    get_service_class,
    list_services,
)
from .configuration import (
    load_di_config,
    get_di_config,
)
from .integration import (
    initialize_di_system,
    shutdown_di_system,
    ensure_di_initialized,
)

__all__ = [
    # Containers
    'ApplicationContainer',
    'ServiceContainer',
    'ClientContainer',
    'ExporterContainer',
    'ProcessorContainer',
    'app_container',
    'get_app_container',
    # Providers
    'LazyEntryPointProvider',
    'ValidatedProvider',
    'ConfigurableProvider',
    # Decorators
    'inject_service',
    'inject_client',
    'inject_exporter',
    'auto_wire',
    # Discovery
    'discover_plugins',
    'register_plugin',
    'list_plugins',
    # Services
    'create_service',
    'create_client',
    'create_exporter',
    'get_service_class',
    'list_services',
    # Configuration
    'load_di_config',
    'get_di_config',
    # Integration
    'initialize_di_system',
    'shutdown_di_system',
    'ensure_di_initialized',
]
