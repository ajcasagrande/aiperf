# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Dynamic Plugin System for AIPerf Lifecycle Components.

This module provides a plugin manager that can discover, load, and manage
AIPerf components dynamically from a plugins directory. All plugins are
managed through the same lifecycle patterns as the core system.

Features:
- Automatic plugin discovery from plugins/ directory
- Dynamic loading of Python modules
- Lifecycle management for all plugins
- Messaging integration between plugins
- Error isolation for faulty plugins
- Plugin metadata and dependencies
- Hot reloading capabilities

Example Plugin Structure:
    plugins/
    ├── my_plugin/
    │   ├── __init__.py
    │   └── plugin.py       # Contains AIPerf components
    ├── data_processor/
    │   ├── __init__.py
    │   ├── processor.py    # Main component
    │   └── config.yaml     # Optional configuration
    └── monitoring/
        ├── __init__.py
        └── monitor.py      # Monitoring service

Each plugin module should export:
- PLUGIN_COMPONENTS: List of component classes to instantiate
- PLUGIN_METADATA: Optional dict with plugin information
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

from .components import BackgroundTasks, Lifecycle, Messaging, Service
from .decorators import background_task, command_handler


class PluginMetadata:
    """
    Metadata for a plugin.

    This contains information about the plugin including its name,
    version, dependencies, and description.
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
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.dependencies = dependencies or []
        self.requires_services = requires_services or []
        self.provides_services = provides_services or []

    def __repr__(self):
        return f"PluginMetadata(name='{self.name}', version='{self.version}')"


class PluginInstance:
    """
    Represents a loaded plugin instance.

    This wraps the actual component instance with metadata and lifecycle state.
    """

    def __init__(
        self,
        name: str,
        component: Any,
        metadata: PluginMetadata,
        module_path: str,
    ):
        self.name = name
        self.component = component
        self.metadata = metadata
        self.module_path = module_path
        self.state = "loaded"
        self.error: Exception | None = None

    @property
    def is_lifecycle_component(self) -> bool:
        """Check if this plugin has lifecycle methods."""
        return hasattr(self.component, "initialize") and hasattr(
            self.component, "start"
        )

    @property
    def component_type(self) -> str:
        """Get the type of component this plugin wraps."""
        if isinstance(self.component, Service):
            return "Service"
        elif isinstance(self.component, Lifecycle):
            return "Lifecycle"
        elif isinstance(self.component, BackgroundTasks):
            return "BackgroundTasks"
        elif isinstance(self.component, Messaging):
            return "Messaging"
        else:
            return "Unknown"

    def __repr__(self):
        return f"PluginInstance(name='{self.name}', type='{self.component_type}', state='{self.state}')"


class PluginManager(Service):
    """
    Dynamic plugin manager for AIPerf lifecycle components.

    This service discovers, loads, and manages plugins from the plugins directory.
    It follows the same lifecycle patterns as other AIPerf components and provides
    messaging capabilities for plugin coordination.

    Example:
        plugin_manager = PluginManager(plugins_dir="./plugins")
        await plugin_manager.initialize()
        await plugin_manager.start()  # Discovers and starts all plugins

        # Query loaded plugins
        plugins = await plugin_manager.send_command("LIST_PLUGINS", plugin_manager.service_id)

        # Stop everything
        await plugin_manager.stop()  # Stops all plugins
    """

    def __init__(
        self, plugins_dir: str | Path = "plugins", auto_reload: bool = False, **kwargs
    ):
        super().__init__(component_id="plugin_manager", **kwargs)
        self.plugins_dir = Path(plugins_dir)
        self.auto_reload = auto_reload

        # Plugin tracking
        self.loaded_plugins: dict[str, PluginInstance] = {}
        self.failed_plugins: dict[str, Exception] = {}
        self.plugin_order: list[str] = []  # Load order for dependencies

        # File monitoring for hot reload
        self._last_scan_time = 0

    async def on_init(self):
        """Initialize the plugin manager."""
        await super().on_init()

        # Create plugins directory if it doesn't exist
        self.plugins_dir.mkdir(exist_ok=True)

        # Create example plugin structure
        await self._create_example_plugins()

        self.logger.info(f"Plugin manager initialized - watching {self.plugins_dir}")

    async def on_start(self):
        """Start the plugin manager and all plugins."""
        await super().on_start()

        # Discover and load all plugins
        await self.discover_and_load_plugins()

        # Start all loaded plugins
        await self.start_all_plugins()

        self.logger.info(
            f"Plugin manager started - {len(self.loaded_plugins)} plugins active"
        )

    async def on_stop(self):
        """Stop the plugin manager and all plugins."""
        # Stop all plugins in reverse order
        await self.stop_all_plugins()

        await super().on_stop()
        self.logger.info("Plugin manager stopped")

    # =================================================================
    # Plugin Discovery and Loading
    # =================================================================

    async def discover_and_load_plugins(self) -> None:
        """Discover and load all plugins from the plugins directory."""
        self.logger.info(f"Scanning for plugins in {self.plugins_dir}")

        if not self.plugins_dir.exists():
            self.logger.warning(f"Plugins directory {self.plugins_dir} does not exist")
            return

        # Find all plugin directories
        plugin_dirs = [
            d
            for d in self.plugins_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

        self.logger.debug(f"Found {len(plugin_dirs)} potential plugin directories")

        # Load each plugin
        for plugin_dir in plugin_dirs:
            try:
                await self._load_plugin_from_directory(plugin_dir)
            except Exception as e:
                self.logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
                self.failed_plugins[plugin_dir.name] = e

        # Resolve dependencies and determine load order
        self._resolve_plugin_dependencies()

        self.logger.info(f"Loaded {len(self.loaded_plugins)} plugins successfully")
        if self.failed_plugins:
            self.logger.warning(f"Failed to load {len(self.failed_plugins)} plugins")

    async def _load_plugin_from_directory(self, plugin_dir: Path) -> None:
        """Load a plugin from a specific directory."""
        plugin_name = plugin_dir.name
        self.logger.debug(f"Loading plugin: {plugin_name}")

        # Look for main plugin file
        plugin_files = [
            plugin_dir / "plugin.py",
            plugin_dir / f"{plugin_name}.py",
            plugin_dir / "__init__.py",
        ]

        plugin_file = None
        for candidate in plugin_files:
            if candidate.exists():
                plugin_file = candidate
                break

        if not plugin_file:
            raise ValueError(f"No plugin file found in {plugin_dir}")

        # Load the module
        module = await self._load_module(plugin_file, plugin_name)

        # Get plugin components and metadata
        components = getattr(module, "PLUGIN_COMPONENTS", [])
        metadata_dict = getattr(module, "PLUGIN_METADATA", {})

        if not components:
            raise ValueError(f"Plugin {plugin_name} has no PLUGIN_COMPONENTS")

        # Create metadata
        # Use plugin_name as default name, but allow override from metadata_dict
        metadata_dict.setdefault("name", plugin_name)
        metadata = PluginMetadata(**metadata_dict)

        # Instantiate components
        for component_class in components:
            if not inspect.isclass(component_class):
                self.logger.warning(f"Skipping non-class component: {component_class}")
                continue

            try:
                # Create component instance with plugin-specific service ID
                component_name = f"{plugin_name}_{component_class.__name__}"

                # Pass appropriate constructor arguments based on component type
                if issubclass(component_class, (Service, Lifecycle)):
                    component = component_class(component_id=component_name)
                elif issubclass(component_class, Messaging):
                    component = component_class(service_id=component_name)
                else:
                    component = component_class()

                # Create plugin instance
                plugin_instance = PluginInstance(
                    name=component_name,
                    component=component,
                    metadata=metadata,
                    module_path=str(plugin_file),
                )

                self.loaded_plugins[component_name] = plugin_instance
                self.logger.debug(
                    f"Loaded component: {component_name} ({plugin_instance.component_type})"
                )

            except Exception as e:
                self.logger.error(f"Failed to instantiate {component_class}: {e}")
                raise

    async def _load_module(self, file_path: Path, module_name: str):
        """Dynamically load a Python module."""
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules temporarily for imports
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
            return module
        except Exception:
            # Clean up on failure
            sys.modules.pop(module_name, None)
            raise

    def _resolve_plugin_dependencies(self) -> None:
        """Resolve plugin dependencies and determine load order."""
        # Simple dependency resolution - can be enhanced for complex dependency graphs
        self.plugin_order = list(self.loaded_plugins.keys())

        # Sort by dependencies (plugins with no dependencies first)
        def dependency_key(plugin_name: str) -> int:
            plugin = self.loaded_plugins[plugin_name]
            return len(plugin.metadata.dependencies)

        self.plugin_order.sort(key=dependency_key)

    # =================================================================
    # Plugin Lifecycle Management
    # =================================================================

    async def start_all_plugins(self) -> None:
        """Start all loaded plugins in dependency order."""
        self.logger.info("Starting all plugins...")

        for plugin_name in self.plugin_order:
            try:
                await self._start_plugin(plugin_name)
            except Exception as e:
                self.logger.error(f"Failed to start plugin {plugin_name}: {e}")
                self.failed_plugins[plugin_name] = e

    async def stop_all_plugins(self) -> None:
        """Stop all plugins in reverse dependency order."""
        self.logger.info("Stopping all plugins...")

        for plugin_name in reversed(self.plugin_order):
            if plugin_name in self.loaded_plugins:
                try:
                    await self._stop_plugin(plugin_name)
                except Exception as e:
                    self.logger.error(f"Failed to stop plugin {plugin_name}: {e}")

    async def _start_plugin(self, plugin_name: str) -> None:
        """Start a specific plugin."""
        plugin = self.loaded_plugins[plugin_name]

        try:
            plugin.state = "starting"

            # Initialize if it's a lifecycle component
            if plugin.is_lifecycle_component:
                if hasattr(plugin.component, "initialize"):
                    await plugin.component.initialize()
                if hasattr(plugin.component, "start"):
                    await plugin.component.start()

            plugin.state = "running"
            plugin.error = None

            self.logger.info(f"Started plugin: {plugin_name} ({plugin.component_type})")

            # Announce plugin started
            await self.publish_message(
                "PLUGIN_STARTED",
                {
                    "plugin_name": plugin_name,
                    "plugin_type": plugin.component_type,
                    "metadata": {
                        "name": plugin.metadata.name,
                        "version": plugin.metadata.version,
                        "description": plugin.metadata.description,
                    },
                },
            )

        except Exception as e:
            plugin.state = "error"
            plugin.error = e
            self.logger.error(f"Failed to start plugin {plugin_name}: {e}")
            raise

    async def _stop_plugin(self, plugin_name: str) -> None:
        """Stop a specific plugin."""
        plugin = self.loaded_plugins[plugin_name]

        try:
            plugin.state = "stopping"

            # Stop if it's a lifecycle component
            if plugin.is_lifecycle_component and hasattr(plugin.component, "stop"):
                await plugin.component.stop()

            plugin.state = "stopped"

            self.logger.info(f"Stopped plugin: {plugin_name}")

            # Announce plugin stopped
            await self.publish_message(
                "PLUGIN_STOPPED",
                {"plugin_name": plugin_name, "plugin_type": plugin.component_type},
            )

        except Exception as e:
            plugin.state = "error"
            plugin.error = e
            self.logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            raise

    # =================================================================
    # Plugin Management Commands
    # =================================================================

    @command_handler("LIST_PLUGINS")
    async def list_plugins(self, command):
        """List all loaded plugins with their status."""
        plugins_info = []

        for name, plugin in self.loaded_plugins.items():
            plugins_info.append(
                {
                    "name": name,
                    "type": plugin.component_type,
                    "state": plugin.state,
                    "metadata": {
                        "name": plugin.metadata.name,
                        "version": plugin.metadata.version,
                        "description": plugin.metadata.description,
                        "author": plugin.metadata.author,
                    },
                    "error": str(plugin.error) if plugin.error else None,
                }
            )

        return {
            "total_plugins": len(self.loaded_plugins),
            "failed_plugins": len(self.failed_plugins),
            "plugins": plugins_info,
        }

    @command_handler("GET_PLUGIN_STATUS")
    async def get_plugin_status(self, command):
        """Get detailed status of a specific plugin."""
        plugin_name = command.content.get("plugin_name")

        if not plugin_name:
            return {"error": "plugin_name required"}

        if plugin_name not in self.loaded_plugins:
            return {"error": f"Plugin {plugin_name} not found"}

        plugin = self.loaded_plugins[plugin_name]

        return {
            "name": plugin.name,
            "type": plugin.component_type,
            "state": plugin.state,
            "module_path": plugin.module_path,
            "metadata": {
                "name": plugin.metadata.name,
                "version": plugin.metadata.version,
                "description": plugin.metadata.description,
                "author": plugin.metadata.author,
                "dependencies": plugin.metadata.dependencies,
                "requires_services": plugin.metadata.requires_services,
                "provides_services": plugin.metadata.provides_services,
            },
            "error": str(plugin.error) if plugin.error else None,
            "component_info": {
                "class_name": plugin.component.__class__.__name__,
                "has_lifecycle": plugin.is_lifecycle_component,
                "service_id": getattr(plugin.component, "service_id", None)
                or getattr(plugin.component, "component_id", None),
            },
        }

    @command_handler("RELOAD_PLUGINS")
    async def reload_plugins(self, command):
        """Reload all plugins (stop, rediscover, start)."""
        self.logger.info("Reloading all plugins...")

        # Stop all current plugins
        await self.stop_all_plugins()

        # Clear plugin state
        self.loaded_plugins.clear()
        self.failed_plugins.clear()
        self.plugin_order.clear()

        # Rediscover and start
        await self.discover_and_load_plugins()
        await self.start_all_plugins()

        return {
            "message": "Plugins reloaded successfully",
            "loaded_plugins": len(self.loaded_plugins),
            "failed_plugins": len(self.failed_plugins),
        }

    # =================================================================
    # Auto-reload Background Task
    # =================================================================

    @background_task(interval=5.0)
    async def check_for_plugin_changes(self):
        """Check for changes in the plugins directory and reload if needed."""
        if not self.auto_reload:
            return

        try:
            # Get current modification time of plugins directory
            current_time = max(
                (f.stat().st_mtime for f in self.plugins_dir.rglob("*.py")), default=0
            )

            if current_time > self._last_scan_time:
                self.logger.info("Plugin files changed - triggering reload")
                await self.reload_plugins(None)
                self._last_scan_time = current_time

        except Exception as e:
            self.logger.error(f"Error checking for plugin changes: {e}")

    # =================================================================
    # Example Plugin Creation
    # =================================================================

    async def _create_example_plugins(self) -> None:
        """Create example plugins if the plugins directory is empty."""
        if any(self.plugins_dir.iterdir()):
            return  # Directory not empty

        self.logger.info("Creating example plugins...")

        # Example 1: Simple message handler plugin
        example1_dir = self.plugins_dir / "hello_world"
        example1_dir.mkdir(exist_ok=True)

        example1_content = '''# Example Hello World Plugin
from aiperf.lifecycle import Service, message_handler, background_task

class HelloWorldService(Service):
    """A simple example plugin that responds to greetings."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.greeting_count = 0

    async def on_init(self):
        await super().on_init()
        self.logger.info("Hello World plugin initialized!")

    async def on_start(self):
        await super().on_start()
        self.logger.info("Hello World plugin started!")

    @message_handler("HELLO")
    async def handle_hello(self, message):
        """Respond to hello messages."""
        self.greeting_count += 1
        sender = message.sender_id or "unknown"

        response = f"Hello {sender}! This is greeting #{self.greeting_count}"
        await self.publish_message("HELLO_RESPONSE", {
            "response": response,
            "count": self.greeting_count
        })

        self.logger.info(f"Responded to hello from {sender}")

    @background_task(interval=30.0)
    async def periodic_greeting(self):
        """Send periodic greetings."""
        await self.publish_message("PERIODIC_HELLO", {
            "message": f"Hello from plugin! Count: {self.greeting_count}",
            "timestamp": __import__('time').time()
        })

# Plugin exports
PLUGIN_COMPONENTS = [HelloWorldService]

PLUGIN_METADATA = {
    "name": "Hello World Plugin",
    "version": "1.0.0",
    "description": "A simple example plugin for testing",
    "author": "AIPerf Team",
    "provides_services": ["greeting", "hello_response"]
}
'''

        (example1_dir / "plugin.py").write_text(example1_content)

        # Example 2: Background task processor
        example2_dir = self.plugins_dir / "data_processor"
        example2_dir.mkdir(exist_ok=True)

        example2_content = '''# Example Data Processor Plugin
from aiperf.lifecycle import Service, message_handler, command_handler, background_task
import asyncio

class DataProcessorService(Service):
    """A data processing plugin that handles work queues."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.work_queue = []
        self.processed_items = 0
        self.processing = False

    async def on_init(self):
        await super().on_init()
        self.logger.info("Data processor plugin initialized!")

    @message_handler("PROCESS_DATA")
    async def handle_process_data(self, message):
        """Add data to processing queue."""
        data = message.content
        self.work_queue.append(data)
        self.logger.info(f"Added data to queue: {len(self.work_queue)} items pending")

        # Acknowledge receipt
        await self.publish_message("DATA_QUEUED", {
            "data_id": data.get("id", "unknown"),
            "queue_size": len(self.work_queue)
        })

    @command_handler("GET_QUEUE_STATUS")
    async def get_queue_status(self, command):
        """Get current queue status."""
        return {
            "queue_size": len(self.work_queue),
            "processed_items": self.processed_items,
            "processing": self.processing
        }

    @background_task(interval=2.0)
    async def process_queue(self):
        """Process items from the work queue."""
        if not self.work_queue or self.processing:
            return

        self.processing = True

        try:
            # Process one item
            item = self.work_queue.pop(0)
            self.logger.info(f"Processing item: {item}")

            # Simulate processing time
            await asyncio.sleep(1.0)

            self.processed_items += 1

            # Notify completion
            await self.publish_message("DATA_PROCESSED", {
                "item": item,
                "processed_count": self.processed_items,
                "remaining": len(self.work_queue)
            })

        finally:
            self.processing = False

# Plugin exports
PLUGIN_COMPONENTS = [DataProcessorService]

PLUGIN_METADATA = {
    "name": "Data Processor Plugin",
    "version": "1.0.0",
    "description": "Processes data items from a queue",
    "author": "AIPerf Team",
    "provides_services": ["data_processing", "queue_management"]
}
'''

        (example2_dir / "plugin.py").write_text(example2_content)

        self.logger.info("Created example plugins: hello_world, data_processor")


# =================================================================
# Utility Functions
# =================================================================


def get_plugin_manager(plugins_dir: str = "plugins", **kwargs) -> PluginManager:
    """Get a plugin manager instance."""
    return PluginManager(plugins_dir=plugins_dir, **kwargs)


async def load_and_start_plugins(
    plugins_dir: str = "plugins", **kwargs
) -> PluginManager:
    """Convenience function to load and start all plugins."""
    manager = get_plugin_manager(plugins_dir, **kwargs)
    await manager.initialize()
    await manager.start()
    return manager
