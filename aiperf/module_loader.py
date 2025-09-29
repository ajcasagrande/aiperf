# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Fast and lazy module loader for AIPerf.

Thread-safe singleton that automatically scans for @Factory.register decorators on first
instantiation, then loads modules on demand. The scan happens only once during singleton
creation, ensuring all subsequent operations are fast and don't need to check scan status.
"""

import ast
import importlib
from enum import Enum
from pathlib import Path

from aiperf.common import enums as aiperf_enums_module
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.meta import SingletonMeta

_logger = AIPerfLogger(__name__)


class ModuleRegistry(metaclass=SingletonMeta):
    """Thread-safe singleton for lazy module loading.

    Automatically scans all Python files for @Factory.register decorators on first
    instantiation. All subsequent operations are guaranteed to have complete registry
    data available without additional scan checks or locks.
    """

    # factory -> {class_type -> module_path}
    _registrations: dict[str, dict[str, str]] = {}
    _initialized = False

    def _init_singleton(self) -> None:
        """Initialize the singleton by scanning all Python files for @Factory.register decorators."""
        self._scan_all()

    def load_plugin(self, factory_name: str, class_type: str | Enum) -> None:
        """Load a plugin module for the given factory and class type."""
        # Convert to string representation - all enums are string enums
        type_key = str(class_type)

        module_path = self._registrations.get(factory_name, {}).get(type_key)
        if module_path:
            importlib.import_module(module_path)

    def get_available_types(self, factory_name: str) -> list[str]:
        """Get all available types for a factory without loading them.

        Args:
            factory_name: Name of the factory to get types for

        Returns:
            List of available type strings for the factory
        """
        if not self._initialized:
            raise RuntimeError("Module registry not initialized")

        return list(self._registrations.get(factory_name, {}).keys())

    def get_all_factories(self) -> list[str]:
        """Get all available factory names.

        Returns:
            List of all factory names that have registered implementations
        """
        if not self._initialized:
            raise RuntimeError("Module registry not initialized")

        return list(self._registrations.keys())

    def load_all_plugins(self, factory_name: str) -> None:
        """Load all available plugins for a factory.

        Args:
            factory_name: Name of the factory to load all plugins for
        """
        if not self._initialized:
            raise RuntimeError("Module registry not initialized")

        factory_registrations = self._registrations.get(factory_name, {})

        # Load all modules for this factory
        for module_path in factory_registrations.values():
            importlib.import_module(module_path)

    def _scan_all(self) -> None:
        """Scan all Python files for @Factory.register decorators.

        This method is only called during singleton instantiation, so no additional
        locking is needed as the instance lock already protects this operation.
        """
        if self._initialized:
            return

        aiperf_root = Path(__file__).parent
        for file_path in aiperf_root.rglob("*.py"):
            if "__pycache__" in str(file_path) or file_path.name == "module_loader.py":
                continue

            try:
                tree = ast.parse(file_path.read_text())
                module_path = f"aiperf.{'.'.join(file_path.relative_to(aiperf_root).with_suffix('').parts)}"

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for decorator in node.decorator_list:
                            self._parse_decorator(decorator, module_path)
            except Exception:
                continue

        self._initialized = True

    def _parse_decorator(self, decorator: ast.expr, module_path: str) -> None:
        """Parse @Factory.register() decorator and store registration."""
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id.endswith("Factory")
            and decorator.func.attr in ["register", "register_all"]
        ):
            factory_name = decorator.func.value.id

            for arg in decorator.args:
                if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                    if factory_name not in self._registrations:
                        self._registrations[factory_name] = {}

                    enum_class_name, enum_value_name = arg.value.id, arg.attr
                    try:
                        # Try to get the actual enum value and store its string representation
                        enum_value = self._get_enum_value(
                            enum_class_name, enum_value_name
                        )
                        self._registrations[factory_name][enum_value] = module_path
                        _logger.debug(
                            f"Registered {enum_class_name}.{enum_value_name} -> '{enum_value}' for {factory_name} in {module_path}"
                        )
                    except Exception:
                        # If we can't resolve the enum, skip it with a warning
                        _logger.warning(
                            f"Could not resolve enum {enum_class_name}.{enum_value_name} for {factory_name} in {module_path}"
                        )

    def _get_enum_value(self, enum_class_name: str, enum_value_name: str) -> str:
        """Returns the string representation of an enum value from the aiperf.common.enums module."""
        if hasattr(aiperf_enums_module, enum_class_name):
            enum_class = getattr(aiperf_enums_module, enum_class_name)
            if hasattr(enum_class, enum_value_name):
                return str(getattr(enum_class, enum_value_name))

        raise ValueError(f"Enum {enum_class_name}.{enum_value_name} not found")
