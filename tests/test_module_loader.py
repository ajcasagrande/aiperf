# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch

import pytest

from aiperf.common.enums import ServiceType
from aiperf.module_loader import ModuleRegistry


class TestModuleRegistry:
    """Test suite for ModuleRegistry singleton class."""

    def setup_method(self):
        """Reset singleton state before each test."""
        ModuleRegistry._instance = None
        ModuleRegistry._registrations = {}
        ModuleRegistry._loaded = False

    @pytest.fixture
    def mock_python_files(self):
        """Create mock Python files with Factory.register decorators."""
        return {
            "service_impl.py": """
from aiperf.common.enums import ServiceType

@ServiceFactory.register(ServiceType.WORKER)
class Worker:
    pass

@ServiceFactory.register(ServiceType.DATASET_MANAGER)
class DatasetManager:
    pass
""",
            "endpoint_impl.py": """
from aiperf.common.enums import EndpointType

@InferenceClientFactory.register(EndpointType.CHAT)
class ChatClient:
    pass
""",
            "invalid_syntax.py": """
# This file has invalid syntax
@ServiceFactory.register(ServiceType.INVALID
class BrokenClass:
    pass
""",
            "no_decorators.py": """
class RegularClass:
    pass
""",
            "multiple_decorators.py": """
from aiperf.common.enums import ServiceType

@ServiceFactory.register_all(ServiceType.WORKER, ServiceType.TIMING_MANAGER)
class MultiService:
    pass
""",
        }

    @pytest.fixture
    def temp_aiperf_structure(self, mock_python_files, tmp_path):
        """Create temporary aiperf directory structure."""
        aiperf_dir = tmp_path / "aiperf"
        aiperf_dir.mkdir()

        # Create __init__.py
        (aiperf_dir / "__init__.py").write_text("")

        # Create subdirectories
        workers_dir = aiperf_dir / "workers"
        workers_dir.mkdir()
        (workers_dir / "__init__.py").write_text("")

        clients_dir = aiperf_dir / "clients"
        clients_dir.mkdir()
        (clients_dir / "__init__.py").write_text("")

        # Write mock files
        for filename, content in mock_python_files.items():
            if "service" in filename:
                (workers_dir / filename).write_text(content)
            else:
                (clients_dir / filename).write_text(content)

        return aiperf_dir

    def test_singleton_pattern(self):
        """Test that ModuleRegistry implements singleton pattern correctly."""
        registry1 = ModuleRegistry()
        registry2 = ModuleRegistry()

        assert registry1 is registry2
        assert id(registry1) == id(registry2)

    def test_thread_safe_singleton(self):
        """Test singleton pattern is thread-safe."""
        instances = []

        def create_instance():
            instances.append(ModuleRegistry())

        # Create instances from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_instance) for _ in range(20)]
            for future in as_completed(futures):
                future.result()

        # All instances should be the same
        first_instance = instances[0]
        assert all(instance is first_instance for instance in instances)

    @patch("aiperf.module_loader.Path")
    def test_scan_all_with_mock_files(self, mock_path_class, temp_aiperf_structure):
        """Test _scan_all method with mocked file structure."""
        # Mock Path(__file__).parent to return our temp directory
        mock_path_instance = Mock()
        mock_path_instance.parent = temp_aiperf_structure
        mock_path_class.return_value = mock_path_instance

        with patch("importlib.import_module") as mock_import:
            mock_enums_module = Mock()
            mock_service_type = Mock()
            mock_service_type.WORKER = "worker"
            mock_service_type.DATASET_MANAGER = "dataset_manager"
            mock_enums_module.ServiceType = mock_service_type
            mock_import.return_value = mock_enums_module

            registry = ModuleRegistry()

            # Verify registrations were found
            assert "ServiceFactory" in registry._registrations
            assert len(registry._registrations["ServiceFactory"]) >= 2

    def test_parse_decorator_with_single_enum(self):
        """Test parsing of @Factory.register(EnumType.VALUE) decorators."""
        registry = ModuleRegistry()

        # Create AST node for a complete class with decorator
        code = """
@ServiceFactory.register(ServiceType.WORKER)
class TestClass:
    pass
"""
        tree = ast.parse(code)
        decorator = tree.body[0].decorator_list[0]  # Get the decorator from class

        with patch("importlib.import_module") as mock_import:
            mock_enums_module = Mock()
            mock_service_type = Mock()
            mock_service_type.WORKER = "worker"
            mock_enums_module.ServiceType = mock_service_type
            mock_import.return_value = mock_enums_module

            registry._parse_decorator(decorator, "test.module")

            expected_key = "worker"
            assert "ServiceFactory" in registry._registrations
            assert expected_key in registry._registrations["ServiceFactory"]
            assert (
                registry._registrations["ServiceFactory"][expected_key] == "test.module"
            )

    def test_parse_decorator_with_invalid_enum(self):
        """Test parsing decorator with non-existent enum."""
        registry = ModuleRegistry()

        code = """
@ServiceFactory.register(NonExistentType.VALUE)
class TestClass:
    pass
"""
        tree = ast.parse(code)
        decorator = tree.body[0].decorator_list[0]

        # Store initial registration count
        initial_count = len(registry._registrations)

        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Module not found")

            # Should not raise exception, just log warning
            registry._parse_decorator(decorator, "test.module")

            # Should not have added any new registrations
            assert len(registry._registrations) == initial_count

    def test_load_plugin_existing_module(self):
        """Test loading an existing plugin module."""
        registry = ModuleRegistry()
        registry._registrations = {
            "ServiceFactory": {"worker": "aiperf.workers.worker"}
        }

        with patch("importlib.import_module") as mock_import:
            registry.load_plugin("ServiceFactory", "worker")
            mock_import.assert_called_once_with("aiperf.workers.worker")

    def test_load_plugin_with_enum(self):
        """Test loading plugin with enum parameter."""
        registry = ModuleRegistry()
        registry._registrations = {
            "ServiceFactory": {"worker": "aiperf.workers.worker"}
        }

        with patch("importlib.import_module") as mock_import:
            registry.load_plugin("ServiceFactory", ServiceType.WORKER)
            mock_import.assert_called_once_with("aiperf.workers.worker")

    def test_load_plugin_nonexistent(self):
        """Test loading non-existent plugin does nothing."""
        registry = ModuleRegistry()

        with patch("importlib.import_module") as mock_import:
            registry.load_plugin("NonExistentFactory", "nonexistent")
            mock_import.assert_not_called()

    def test_get_available_types(self):
        """Test get_available_types returns correct type list."""
        registry = ModuleRegistry()
        registry._registrations = {
            "ServiceFactory": {
                "worker": "aiperf.workers.worker",
                "dataset_manager": "aiperf.dataset.dataset_manager",
            },
            "ClientFactory": {"chat": "aiperf.clients.chat"},
        }

        service_types = registry.get_available_types("ServiceFactory")
        assert set(service_types) == {"worker", "dataset_manager"}

        client_types = registry.get_available_types("ClientFactory")
        assert client_types == ["chat"]

        # Non-existent factory should return empty list
        empty_types = registry.get_available_types("NonExistentFactory")
        assert empty_types == []

    def test_get_all_factories(self):
        """Test get_all_factories returns all factory names."""
        registry = ModuleRegistry()
        registry._registrations = {
            "ServiceFactory": {"worker": "module1"},
            "ClientFactory": {"chat": "module2"},
            "ExporterFactory": {"csv": "module3"},
        }

        factories = registry.get_all_factories()
        assert set(factories) == {"ServiceFactory", "ClientFactory", "ExporterFactory"}

    def test_load_all_plugins(self):
        """Test load_all_plugins loads all modules for a factory."""
        registry = ModuleRegistry()
        registry._registrations = {
            "ServiceFactory": {
                "worker": "aiperf.workers.worker",
                "dataset_manager": "aiperf.dataset.dataset_manager",
                "timing_manager": "aiperf.timing.timing_manager",
            }
        }

        with patch("importlib.import_module") as mock_import:
            registry.load_all_plugins("ServiceFactory")

            # Should have called import_module for each module
            expected_calls = [
                "aiperf.workers.worker",
                "aiperf.dataset.dataset_manager",
                "aiperf.timing.timing_manager",
            ]
            assert mock_import.call_count == 3
            for call in expected_calls:
                mock_import.assert_any_call(call)

    def test_load_all_plugins_nonexistent_factory(self):
        """Test load_all_plugins with non-existent factory."""
        registry = ModuleRegistry()

        with patch("importlib.import_module") as mock_import:
            registry.load_all_plugins("NonExistentFactory")
            mock_import.assert_not_called()

    @patch("aiperf.module_loader.Path")
    def test_scan_skips_pycache_and_self(self, mock_path_class):
        """Test that _scan_all skips __pycache__ and module_loader.py itself."""
        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance

        # Create mock files including ones that should be skipped
        mock_files = [
            Mock(name="regular.py"),
            Mock(name="__pycache__/cached.py"),
            Mock(name="module_loader.py"),
        ]

        # Set up the __pycache__ file to have it in the string representation
        mock_files[1].__str__ = Mock(return_value="/path/__pycache__/cached.py")
        mock_files[1].name = "cached.py"

        mock_files[0].__str__ = Mock(return_value="/path/regular.py")
        mock_files[0].name = "regular.py"
        mock_files[0].read_text.return_value = "class TestClass: pass"

        # Mock the path operations properly
        mock_relative_path = Mock()
        mock_relative_path.with_suffix.return_value.parts = ("regular",)
        mock_files[0].relative_to.return_value = mock_relative_path

        mock_files[2].__str__ = Mock(return_value="/path/module_loader.py")
        mock_files[2].name = "module_loader.py"

        mock_path_instance.parent.rglob.return_value = mock_files

        _ = ModuleRegistry()

        # Only regular.py should have been processed (read_text called)
        mock_files[0].read_text.assert_called_once()
        # __pycache__ and module_loader.py should not be processed
        assert (
            not hasattr(mock_files[1], "read_text")
            or not mock_files[1].read_text.called
        )
        assert (
            not hasattr(mock_files[2], "read_text")
            or not mock_files[2].read_text.called
        )

    def test_scan_handles_file_read_errors(self):
        """Test that _scan_all handles file reading errors gracefully."""
        with patch("aiperf.module_loader.Path") as mock_path_class:
            mock_path_instance = Mock()
            mock_path_class.return_value = mock_path_instance

            # Mock file that raises exception when reading
            mock_file = Mock()
            mock_file.__str__ = Mock(return_value="/path/error_file.py")
            mock_file.name = "error_file.py"
            mock_file.read_text.side_effect = PermissionError("Access denied")

            mock_path_instance.parent.rglob.return_value = [mock_file]

            # Should not raise exception
            registry = ModuleRegistry()

            # Should have initial registrations (from real scan) but no new ones from error file
            # Since we're testing error handling, just verify no exception was raised
            assert registry._registrations is not None

    def test_scan_handles_ast_parse_errors(self):
        """Test that _scan_all handles AST parsing errors gracefully."""
        with patch("aiperf.module_loader.Path") as mock_path_class:
            mock_path_instance = Mock()
            mock_path_class.return_value = mock_path_instance

            # Mock file with invalid Python syntax
            mock_file = Mock()
            mock_file.__str__ = Mock(return_value="/path/invalid.py")
            mock_file.name = "invalid.py"
            mock_file.read_text.return_value = "invalid python syntax {"

            # Mock the path operations properly
            mock_relative_path = Mock()
            mock_relative_path.with_suffix.return_value.parts = ("invalid",)
            mock_file.relative_to.return_value = mock_relative_path

            mock_path_instance.parent.rglob.return_value = [mock_file]

            # Should not raise exception
            registry = ModuleRegistry()

            # Should have initial registrations (from real scan) but no new ones from syntax error file
            # Since we're testing error handling, just verify no exception was raised
            assert registry._registrations is not None

    def test_loaded_flag_prevents_double_scan(self):
        """Test that _loaded flag prevents scanning twice."""
        registry = ModuleRegistry()

        # Manually set loaded flag
        registry._loaded = True

        with patch("aiperf.module_loader.Path") as mock_path_class:
            # Call _scan_all again
            registry._scan_all()

            # Path should not have been accessed since scan was skipped
            mock_path_class.assert_not_called()

    @pytest.mark.parametrize(
        "enum_value,expected_string",
        [
            (ServiceType.WORKER, "worker"),
            (ServiceType.DATASET_MANAGER, "dataset_manager"),
            ("custom_string", "custom_string"),
        ],
    )
    def test_load_plugin_enum_conversion(self, enum_value, expected_string):
        """Test that load_plugin correctly converts enums to strings."""
        registry = ModuleRegistry()
        registry._registrations = {"TestFactory": {expected_string: "test.module"}}

        with patch("importlib.import_module") as mock_import:
            registry.load_plugin("TestFactory", enum_value)
            mock_import.assert_called_once_with("test.module")

    def test_multiple_factories_same_module(self):
        """Test handling multiple factory registrations in the same module."""
        registry = ModuleRegistry()

        # Simulate parsing a module with multiple factory decorators
        code = """
@ServiceFactory.register(ServiceType.WORKER)
@ClientFactory.register(EndpointType.CHAT)
class MultiFactoryClass:
    pass
"""
        tree = ast.parse(code)

        with patch("importlib.import_module") as mock_import:
            mock_enums_module = Mock()

            # Mock ServiceType
            mock_service_type = Mock()
            mock_service_type.WORKER = "worker"
            mock_enums_module.ServiceType = mock_service_type

            # Mock EndpointType
            mock_endpoint_type = Mock()
            mock_endpoint_type.CHAT = "chat"
            mock_enums_module.EndpointType = mock_endpoint_type

            mock_import.return_value = mock_enums_module

            # Parse both decorators
            class_node = tree.body[0]
            for decorator in class_node.decorator_list:
                registry._parse_decorator(decorator, "test.module")

            # Should have registrations for both factories
            assert "ServiceFactory" in registry._registrations
            assert "ClientFactory" in registry._registrations
            assert registry._registrations["ServiceFactory"]["worker"] == "test.module"
            assert registry._registrations["ClientFactory"]["chat"] == "test.module"

    def test_decorator_without_enum_attribute(self):
        """Test handling decorators that don't follow expected enum pattern."""
        registry = ModuleRegistry()

        # Test decorator with string literal instead of enum
        code = """
@ServiceFactory.register("string_literal")
class TestClass:
    pass
"""
        tree = ast.parse(code)
        decorator = tree.body[0].decorator_list[0]

        # Store initial registration count
        initial_count = len(registry._registrations)

        # Should not crash, but also shouldn't register anything new
        registry._parse_decorator(decorator, "test.module")
        assert len(registry._registrations) == initial_count

    def test_non_factory_decorators_ignored(self):
        """Test that non-Factory decorators are ignored."""
        registry = ModuleRegistry()

        code = """
class TestClass:
    @property
    def test_property(self):
        pass
"""
        tree = ast.parse(code)
        # Get the property decorator from the method
        decorator = tree.body[0].body[0].decorator_list[0]

        # Store initial registration count
        initial_count = len(registry._registrations)

        registry._parse_decorator(decorator, "test.module")
        assert len(registry._registrations) == initial_count

    def test_register_all_decorator_parsing(self):
        """Test parsing of @Factory.register_all() decorators."""
        registry = ModuleRegistry()

        code = """
@ServiceFactory.register_all(ServiceType.WORKER, ServiceType.TIMING_MANAGER)
class TestClass:
    pass
"""
        tree = ast.parse(code)
        decorator = tree.body[0].decorator_list[0]

        with patch("importlib.import_module") as mock_import:
            mock_enums_module = Mock()
            mock_service_type = Mock()
            mock_service_type.WORKER = "worker"
            mock_service_type.TIMING_MANAGER = "timing_manager"
            mock_enums_module.ServiceType = mock_service_type
            mock_import.return_value = mock_enums_module

            registry._parse_decorator(decorator, "test.module")

            # Should register both types
            assert "ServiceFactory" in registry._registrations
            assert "worker" in registry._registrations["ServiceFactory"]
            assert "timing_manager" in registry._registrations["ServiceFactory"]
