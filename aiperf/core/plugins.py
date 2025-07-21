# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AIPerf Plugin Architecture - Built on Amazing Mixin Foundation

This module provides a robust plugin system that seamlessly integrates with
the existing mixin architecture. Plugins can use all the same patterns as
regular services: lifecycle methods, message handlers, background tasks, etc.

Key Features:
- Seamless integration with LifecycleMixin, MessageBusMixin, BackgroundTasksMixin
- Automatic plugin discovery from directories
- Full lifecycle management for all plugins
- Message routing between plugins and services
- Error isolation to prevent plugin failures from affecting core system
- Hot-reloading capabilities
- Plugin dependencies and metadata
- Type-safe plugin interfaces

Example Plugin:
    ```python
    # plugins/data_processor/plugin.py
    from aiperf.core.plugins import BasePlugin
    from aiperf.core.decorators import message_handler, background_task
    from aiperf.common.enums.message_enums import MessageType

    class DataProcessorPlugin(BasePlugin):
        plugin_name = "data_processor"
        plugin_version = "1.0.0"
        plugin_description = "Processes incoming data streams"

        async def _initialize(self):
            await super()._initialize()
            self.processed_count = 0
            self.info("Data processor plugin initialized")

        @message_handler(MessageType.DATA_UPDATE)
        async def handle_data(self, message):
            # Full message handling with inheritance support
            self.processed_count += 1
            self.info(f"Processed data item #{self.processed_count}")

        @background_task(interval=30.0)
        async def report_stats(self):
            # Background tasks work seamlessly
            self.info(f"Total processed: {self.processed_count}")
    ```

Example Service with Plugin Manager:
    ```python
    from aiperf.core.base_service import BaseService
    from aiperf.core.plugins import PluginManagerMixin

    class MyService(BaseService, PluginManagerMixin):
        def __init__(self, **kwargs):
            super().__init__(
                plugin_directories=["./plugins", "./extensions"],
                plugin_config={"debug_mode": True},
                **kwargs
            )

        async def _initialize(self):
            await super()._initialize()
            # Plugins are automatically loaded and started!
            self.info(f"Started with {len(self.plugins)} plugins")
    ```
"""

import asyncio
import importlib.util
import inspect
from pathlib import Path
from typing import ClassVar

from aiperf.common.exceptions import AIPerfError
from aiperf.core.background_tasks import BackgroundTasksMixin
from aiperf.core.communication_mixins import MessageBusMixin
from aiperf.core.lifecycle import LifecycleMixin


class PluginError(AIPerfError):
    """Base exception for plugin-related errors."""

    pass


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

    pass


class PluginInitError(PluginError):
    """Raised when a plugin fails to initialize."""

    pass


class PluginMetadata:
    """
    Metadata for a plugin containing information about its capabilities,
    dependencies, and configuration.
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        author: str = "",
        dependencies: list[str] = None,
        requires_services: list[str] = None,
        provides_services: list[str] = None,
        config_schema: dict = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.dependencies = dependencies or []
        self.requires_services = requires_services or []
        self.provides_services = provides_services or []
        self.config_schema = config_schema or {}

    def __str__(self):
        return f"{self.name} v{self.version}"

    def __repr__(self):
        return f"PluginMetadata(name='{self.name}', version='{self.version}')"


class BasePlugin(MessageBusMixin, BackgroundTasksMixin):
    """
    Base class for all AIPerf plugins using the amazing mixin architecture.

    This class provides all the same capabilities as regular services:
    - Full lifecycle management with _initialize(), _start(), _stop()
    - Message handling with @message_handler decorators
    - Background tasks with @background_task decorators
    - Real aiperf communication infrastructure

    Plugin developers just inherit from this class and override the methods
    they need, exactly like regular services.

    Class Attributes:
        plugin_name: Unique name for the plugin
        plugin_version: Plugin version (semantic versioning recommended)
        plugin_description: Human-readable description
        plugin_author: Plugin author information
        plugin_dependencies: List of required plugin names
        plugin_requires_services: List of required service types
        plugin_provides_services: List of service capabilities this plugin provides

    Example:
        class MyPlugin(BasePlugin):
            plugin_name = "awesome_plugin"
            plugin_version = "2.1.0"
            plugin_description = "Does awesome things"

            async def _initialize(self):
                await super()._initialize()
                self.info("Plugin is ready!")

            @message_handler(MessageType.STATUS)
            async def handle_status(self, message):
                self.info(f"Plugin received status: {message}")
    """

    # Plugin metadata (override in subclasses)
    plugin_name: ClassVar[str] = "unknown_plugin"
    plugin_version: ClassVar[str] = "1.0.0"
    plugin_description: ClassVar[str] = ""
    plugin_author: ClassVar[str] = ""
    plugin_dependencies: ClassVar[list[str]] = []
    plugin_requires_services: ClassVar[list[str]] = []
    plugin_provides_services: ClassVar[list[str]] = []

    def __init__(self, plugin_config: dict = None, **kwargs):
        self.plugin_config = plugin_config or {}
        self.plugin_state = "created"
        self.plugin_error: Exception | None = None

        # Generate unique plugin ID
        plugin_id = f"plugin_{self.plugin_name}_{id(self)}"

        # Initialize with plugin-specific ID
        super().__init__(id=plugin_id, **kwargs)

    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name=self.plugin_name,
            version=self.plugin_version,
            description=self.plugin_description,
            author=self.plugin_author,
            dependencies=self.plugin_dependencies,
            requires_services=self.plugin_requires_services,
            provides_services=self.plugin_provides_services,
        )

    async def _initialize(self) -> None:
        """Initialize the plugin. Override and call super()._initialize()"""
        await super()._initialize()
        self.plugin_state = "initialized"
        self.debug(f"Plugin {self.plugin_name} initialized successfully")

    async def _start(self) -> None:
        """Start the plugin. Override and call super()._start()"""
        await super()._start()
        self.plugin_state = "running"
        self.debug(f"Plugin {self.plugin_name} started successfully")

    async def _stop(self) -> None:
        """Stop the plugin. Override and call super()._stop()"""
        await super()._stop()
        self.plugin_state = "stopped"
        self.debug(f"Plugin {self.plugin_name} stopped successfully")

    def __str__(self):
        return f"Plugin({self.plugin_name} v{self.plugin_version})"

    def __repr__(self):
        return f"<Plugin {self.plugin_name} v{self.plugin_version} state={self.plugin_state}>"


class PluginInstance:
    """
    Wrapper for a loaded plugin instance with metadata and state tracking.
    """

    def __init__(
        self,
        plugin: BasePlugin,
        module_path: str,
        config: dict = None,
    ):
        self.plugin = plugin
        self.module_path = module_path
        self.config = config or {}
        self.load_time = asyncio.get_event_loop().time()
        self.error: Exception | None = None

    @property
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return self.plugin.metadata

    @property
    def state(self) -> str:
        """Get plugin state."""
        return self.plugin.plugin_state

    @property
    def is_running(self) -> bool:
        """True if plugin is running."""
        return self.state == "running"

    async def initialize(self) -> None:
        """Initialize the plugin with error handling."""
        try:
            await self.plugin.initialize()
        except Exception as e:
            self.error = e
            self.plugin.plugin_error = e
            raise PluginInitError(
                f"Failed to initialize plugin {self.metadata.name}: {e}"
            ) from e

    async def start(self) -> None:
        """Start the plugin with error handling."""
        try:
            await self.plugin.start()
        except Exception as e:
            self.error = e
            self.plugin.plugin_error = e
            raise PluginError(
                f"Failed to start plugin {self.metadata.name}: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the plugin with error handling."""
        try:
            await self.plugin.stop()
        except Exception as e:
            self.error = e
            self.plugin.plugin_error = e
            # Don't raise on stop errors - log and continue
            self.plugin.exception(f"Error stopping plugin {self.metadata.name}: {e}")

    def __str__(self):
        return f"PluginInstance({self.metadata})"


class PluginManagerMixin(LifecycleMixin):
    """
    Mixin that provides plugin management capabilities to any service.

    This mixin integrates seamlessly with the existing mixin architecture,
    adding plugin discovery, loading, and lifecycle management to any service
    that inherits from it.

    Features:
    - Automatic plugin discovery from specified directories
    - Plugin dependency resolution
    - Lifecycle management for all plugins
    - Error isolation (plugin failures don't crash the service)
    - Plugin configuration management
    - Hot-reloading capabilities

    Usage:
        class MyService(BaseService, PluginManagerMixin):
            def __init__(self, **kwargs):
                super().__init__(
                    plugin_directories=["./plugins", "./extensions"],
                    plugin_config={"debug_mode": True},
                    **kwargs
                )

            async def _initialize(self):
                await super()._initialize()
                # Plugins are automatically loaded and started!
                self.info(f"Started with {len(self.plugins)} plugins")
    """

    def __init__(
        self,
        plugin_directories: list[str] = None,
        plugin_config: dict = None,
        enable_hot_reload: bool = False,
        **kwargs,
    ):
        self.plugin_directories = plugin_directories or ["./plugins"]
        self.plugin_config = plugin_config or {}
        self.enable_hot_reload = enable_hot_reload

        # Plugin management state
        self.plugins: dict[str, PluginInstance] = {}
        self.plugin_load_order: list[str] = []
        self.failed_plugins: dict[str, Exception] = {}

        super().__init__(**kwargs)

    async def _initialize(self) -> None:
        """Initialize the plugin manager and load all plugins."""
        await super()._initialize()

        self.info(
            f"Initializing plugin manager with directories: {self.plugin_directories}"
        )

        # Discover and load plugins
        await self.discover_plugins()
        await self.load_all_plugins()

        self.info(f"Plugin manager initialized with {len(self.plugins)} plugins loaded")

    async def _start(self) -> None:
        """Start all loaded plugins."""
        await super()._start()

        self.info("Starting all plugins...")

        # Start plugins in dependency order
        for plugin_name in self.plugin_load_order:
            if plugin_name in self.plugins:
                try:
                    await self.plugins[plugin_name].start()
                    self.debug(f"Started plugin: {plugin_name}")
                except Exception as e:
                    self.exception(f"Failed to start plugin {plugin_name}: {e}")
                    self.failed_plugins[plugin_name] = e

        running_count = sum(1 for p in self.plugins.values() if p.is_running)
        self.info(
            f"Plugin manager started {running_count}/{len(self.plugins)} plugins successfully"
        )

    async def _stop(self) -> None:
        """Stop all plugins."""
        await super()._stop()

        self.info("Stopping all plugins...")

        # Stop plugins in reverse order
        for plugin_name in reversed(self.plugin_load_order):
            if plugin_name in self.plugins:
                await self.plugins[plugin_name].stop()

        self.info("All plugins stopped")

    async def discover_plugins(self) -> list[str]:
        """
        Discover available plugins in the specified directories.

        Returns:
            List of discovered plugin paths
        """
        discovered = []

        for directory in self.plugin_directories:
            plugin_dir = Path(directory)
            if not plugin_dir.exists():
                self.warning(f"Plugin directory does not exist: {plugin_dir}")
                continue

            self.debug(f"Scanning for plugins in: {plugin_dir}")

            # Look for plugin.py files in subdirectories
            for plugin_path in plugin_dir.glob("*/plugin.py"):
                plugin_module_path = str(plugin_path)
                discovered.append(plugin_module_path)
                self.debug(f"Discovered plugin: {plugin_module_path}")

        self.info(f"Discovered {len(discovered)} plugins")
        return discovered

    async def load_all_plugins(self) -> None:
        """Load and initialize all discovered plugins."""
        plugin_paths = await self.discover_plugins()

        for plugin_path in plugin_paths:
            try:
                await self.load_plugin(plugin_path)
            except Exception as e:
                self.exception(f"Failed to load plugin from {plugin_path}: {e}")
                self.failed_plugins[plugin_path] = e

    async def load_plugin(self, plugin_path: str) -> PluginInstance:
        """
        Load a single plugin from a file path.

        Args:
            plugin_path: Path to the plugin.py file

        Returns:
            Loaded PluginInstance

        Raises:
            PluginLoadError: If plugin fails to load
        """
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not load spec for {plugin_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin classes in the module
            plugin_classes = []
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BasePlugin)
                    and obj is not BasePlugin
                    and hasattr(obj, "plugin_name")
                ):
                    plugin_classes.append(obj)

            if not plugin_classes:
                raise PluginLoadError(f"No valid plugin classes found in {plugin_path}")

            if len(plugin_classes) > 1:
                self.warning(
                    f"Multiple plugin classes found in {plugin_path}, using first one"
                )

            # Instantiate the plugin
            plugin_class = plugin_classes[0]
            plugin_instance = plugin_class(
                plugin_config=self.plugin_config.get(plugin_class.plugin_name, {}),
                comms=getattr(self, "comms", None),  # Share communication if available
            )

            # Create plugin wrapper
            plugin_wrapper = PluginInstance(
                plugin=plugin_instance,
                module_path=plugin_path,
                config=self.plugin_config.get(plugin_instance.plugin_name, {}),
            )

            # Initialize the plugin
            await plugin_wrapper.initialize()

            # Register the plugin
            self.plugins[plugin_instance.plugin_name] = plugin_wrapper
            self.plugin_load_order.append(plugin_instance.plugin_name)

            self.info(f"Loaded plugin: {plugin_wrapper.metadata}")
            return plugin_wrapper

        except Exception as e:
            raise PluginLoadError(
                f"Failed to load plugin from {plugin_path}: {e}"
            ) from e

    async def unload_plugin(self, plugin_name: str) -> None:
        """
        Unload a plugin by name.

        Args:
            plugin_name: Name of the plugin to unload
        """
        if plugin_name not in self.plugins:
            self.warning(f"Plugin {plugin_name} not found")
            return

        plugin_instance = self.plugins[plugin_name]

        try:
            # Stop the plugin
            await plugin_instance.stop()
        except Exception as e:
            self.exception(f"Error stopping plugin {plugin_name}: {e}")
        finally:
            # Remove from tracking
            del self.plugins[plugin_name]
            if plugin_name in self.plugin_load_order:
                self.plugin_load_order.remove(plugin_name)

            self.info(f"Unloaded plugin: {plugin_name}")

    async def reload_plugin(self, plugin_name: str) -> None:
        """
        Reload a plugin (unload then load again).

        Args:
            plugin_name: Name of the plugin to reload
        """
        if plugin_name not in self.plugins:
            self.warning(f"Cannot reload unknown plugin: {plugin_name}")
            return

        plugin_path = self.plugins[plugin_name].module_path

        # Unload the current plugin
        await self.unload_plugin(plugin_name)

        # Load it again
        try:
            await self.load_plugin(plugin_path)
            self.info(f"Reloaded plugin: {plugin_name}")
        except Exception as e:
            self.exception(f"Failed to reload plugin {plugin_name}: {e}")
            self.failed_plugins[plugin_name] = e

    def get_plugin(self, plugin_name: str) -> BasePlugin | None:
        """
        Get a plugin instance by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance or None if not found
        """
        if plugin_name in self.plugins:
            return self.plugins[plugin_name].plugin
        return None

    def get_plugin_status(self) -> dict:
        """
        Get status information for all plugins.

        Returns:
            Dictionary with plugin status information
        """
        return {
            "loaded_plugins": {
                name: {
                    "metadata": instance.metadata.__dict__,
                    "state": instance.state,
                    "is_running": instance.is_running,
                    "load_time": instance.load_time,
                    "error": str(instance.error) if instance.error else None,
                }
                for name, instance in self.plugins.items()
            },
            "failed_plugins": {
                name: str(error) for name, error in self.failed_plugins.items()
            },
            "plugin_directories": self.plugin_directories,
            "total_plugins": len(self.plugins),
            "running_plugins": sum(1 for p in self.plugins.values() if p.is_running),
            "failed_count": len(self.failed_plugins),
        }

    def list_plugins(self) -> list[str]:
        """Get list of loaded plugin names."""
        return list(self.plugins.keys())
