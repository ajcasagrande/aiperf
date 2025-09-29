# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Plugin system for AIPerf using pluggy."""

from aiperf.common.plugins.base import (
    BaseRequestConverterPlugin,
    hookimpl,
    register_plugin_class,
    register_plugin_instance,
    request_converter_plugin,
)
from aiperf.common.plugins.cli import (
    discover_plugins,
    list_plugins,
    list_supported_types,
    plugins_cli,
    system_info,
    test_endpoint,
)
from aiperf.common.plugins.factory import (
    PluggyRequestConverterAdapter,
    PluggyRequestConverterFactory,
    get_pluggy_factory,
)
from aiperf.common.plugins.hookspecs import (
    PROJECT_NAME,
    RequestConverterHookSpec,
    hookspec,
)
from aiperf.common.plugins.hybrid_factory import (
    HybridRequestConverterFactory,
    get_hybrid_factory,
)
from aiperf.common.plugins.manager import (
    PluginNotFoundError,
    RequestConverterPluginManager,
    get_plugin_manager,
)

__all__ = [
    "BaseRequestConverterPlugin",
    "HybridRequestConverterFactory",
    "PROJECT_NAME",
    "PluggyRequestConverterAdapter",
    "PluggyRequestConverterFactory",
    "PluginNotFoundError",
    "RequestConverterHookSpec",
    "RequestConverterPluginManager",
    "discover_plugins",
    "get_hybrid_factory",
    "get_pluggy_factory",
    "get_plugin_manager",
    "hookimpl",
    "hookspec",
    "list_plugins",
    "list_supported_types",
    "plugins_cli",
    "register_plugin_class",
    "register_plugin_instance",
    "request_converter_plugin",
    "system_info",
    "test_endpoint",
]
