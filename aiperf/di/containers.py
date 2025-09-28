# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Dependency injection containers for AIPerf services and components."""

import importlib.metadata
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol
else:
    try:
        from typing import Protocol
    except ImportError:
        from typing_extensions import Protocol

from dependency_injector import containers, providers
from pydantic import BaseModel

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.di.providers import LazyEntryPointProvider, create_lazy_provider
from aiperf.di.discovery import discover_entry_points

logger = AIPerfLogger(__name__)


class BaseContainer(containers.DeclarativeContainer):
    """Base container with common functionality."""

    # Configuration provider
    config = providers.Configuration()

    @classmethod
    def discover_and_register(
        cls,
        entry_point_group: str,
        provider_type: str = "factory",
        expected_protocol: Optional[Type["Protocol"]] = None
    ) -> None:
        """Discover and register plugins from entry points."""
        entry_points = discover_entry_points(entry_point_group)

        for ep_name, ep_info in entry_points.items():
            provider = create_lazy_provider(
                entry_point_name=ep_name,
                entry_point_group=entry_point_group,
                provider_type=provider_type,
                expected_protocol=expected_protocol
            )

            # Register provider as container attribute
            setattr(cls, ep_name, provider)
            logger.debug(f"Registered {ep_name} in {cls.__name__}")


class ServiceContainer(BaseContainer):
    """Container for AIPerf services."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "aiperf.controller",
            "aiperf.workers",
            "aiperf.dataset",
            "aiperf.timing",
            "aiperf.records",
        ]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-discover services on container creation
        cls._discover_services()

    @classmethod
    def _discover_services(cls) -> None:
        """Discover and register all services."""
        from aiperf.common.protocols import ServiceProtocol
        cls.discover_and_register(
            entry_point_group="aiperf.services",
            provider_type="factory",
            expected_protocol=ServiceProtocol
        )


class ClientContainer(BaseContainer):
    """Container for inference and communication clients."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "aiperf.clients",
            "aiperf.zmq",
        ]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._discover_clients()

    @classmethod
    def _discover_clients(cls) -> None:
        """Discover and register all clients."""
        from aiperf.common.protocols import InferenceClientProtocol, CommunicationClientProtocol

        # Inference clients
        cls.discover_and_register(
            entry_point_group="aiperf.inference_clients",
            provider_type="factory",
            expected_protocol=InferenceClientProtocol
        )

        # Communication clients
        cls.discover_and_register(
            entry_point_group="aiperf.communication_clients",
            provider_type="factory",
            expected_protocol=CommunicationClientProtocol
        )

        # General clients
        cls.discover_and_register(
            entry_point_group="aiperf.clients",
            provider_type="factory"
        )


class ExporterContainer(BaseContainer):
    """Container for data exporters and console exporters."""

    wiring_config = containers.WiringConfiguration(
        modules=["aiperf.exporters"]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._discover_exporters()

    @classmethod
    def _discover_exporters(cls) -> None:
        """Discover and register all exporters."""
        from aiperf.common.protocols import DataExporterProtocol, ConsoleExporterProtocol

        # Data exporters
        cls.discover_and_register(
            entry_point_group="aiperf.exporters",
            provider_type="factory",
            expected_protocol=DataExporterProtocol
        )

        # Console exporters
        cls.discover_and_register(
            entry_point_group="aiperf.console_exporters",
            provider_type="factory",
            expected_protocol=ConsoleExporterProtocol
        )


class ProcessorContainer(BaseContainer):
    """Container for record and results processors."""

    wiring_config = containers.WiringConfiguration(
        modules=["aiperf.post_processors"]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._discover_processors()

    @classmethod
    def _discover_processors(cls) -> None:
        """Discover and register all processors."""
        from aiperf.common.protocols import RecordProcessorProtocol, ResultsProcessorProtocol

        # Record processors
        cls.discover_and_register(
            entry_point_group="aiperf.record_processors",
            provider_type="factory",
            expected_protocol=RecordProcessorProtocol
        )

        # Results processors
        cls.discover_and_register(
            entry_point_group="aiperf.results_processors",
            provider_type="factory",
            expected_protocol=ResultsProcessorProtocol
        )

        # General processors
        cls.discover_and_register(
            entry_point_group="aiperf.processors",
            provider_type="factory"
        )


class UIContainer(BaseContainer):
    """Container for user interface components."""

    wiring_config = containers.WiringConfiguration(
        modules=["aiperf.ui"]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._discover_ui_components()

    @classmethod
    def _discover_ui_components(cls) -> None:
        """Discover and register UI components."""
        from aiperf.common.protocols import AIPerfUIProtocol

        cls.discover_and_register(
            entry_point_group="aiperf.ui",
            provider_type="singleton",  # UI components are typically singletons
            expected_protocol=AIPerfUIProtocol
        )


class ComposerContainer(BaseContainer):
    """Container for dataset composers."""

    wiring_config = containers.WiringConfiguration(
        modules=["aiperf.dataset.composer"]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._discover_composers()

    @classmethod
    def _discover_composers(cls) -> None:
        """Discover and register dataset composers."""
        cls.discover_and_register(
            entry_point_group="aiperf.composers",
            provider_type="factory"
        )


class ServiceManagerContainer(BaseContainer):
    """Container for service managers."""

    wiring_config = containers.WiringConfiguration(
        modules=["aiperf.controller"]
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._discover_service_managers()

    @classmethod
    def _discover_service_managers(cls) -> None:
        """Discover and register service managers."""
        from aiperf.common.protocols import ServiceManagerProtocol

        cls.discover_and_register(
            entry_point_group="aiperf.service_managers",
            provider_type="factory",
            expected_protocol=ServiceManagerProtocol
        )


class ApplicationContainer(BaseContainer):
    """Main application container that aggregates all other containers."""

    # Child containers
    services = providers.DependenciesContainer()
    clients = providers.DependenciesContainer()
    exporters = providers.DependenciesContainer()
    processors = providers.DependenciesContainer()
    ui = providers.DependenciesContainer()
    composers = providers.DependenciesContainer()
    service_managers = providers.DependenciesContainer()

    wiring_config = containers.WiringConfiguration(
        modules=[
            "aiperf.controller",
            "aiperf.workers",
            "aiperf.dataset",
            "aiperf.timing",
            "aiperf.records",
            "aiperf.clients",
            "aiperf.exporters",
            "aiperf.post_processors",
            "aiperf.ui",
            "aiperf.zmq",
        ]
    )

    def __init__(self) -> None:
        super().__init__()
        self._initialize_containers()

    def _initialize_containers(self) -> None:
        """Initialize all child containers."""
        # Create instances of specialized containers
        service_container = ServiceContainer()
        client_container = ClientContainer()
        exporter_container = ExporterContainer()
        processor_container = ProcessorContainer()
        ui_container = UIContainer()
        composer_container = ComposerContainer()
        service_manager_container = ServiceManagerContainer()

        # Wire child containers to this container
        self.services.override(service_container)
        self.clients.override(client_container)
        self.exporters.override(exporter_container)
        self.processors.override(processor_container)
        self.ui.override(ui_container)
        self.composers.override(composer_container)
        self.service_managers.override(service_manager_container)

        logger.info("Application container initialized with all child containers")

    def get_service(self, service_name: str, **kwargs: Any) -> Any:
        """Get service instance by name."""
        if not hasattr(self.services.provided, service_name):
            available = [name for name in dir(self.services.provided) if not name.startswith('_')]
            raise ValueError(f"Service '{service_name}' not found. Available: {available}")

        provider = getattr(self.services.provided, service_name)
        return provider(**kwargs)

    def get_client(self, client_name: str, **kwargs: Any) -> Any:
        """Get client instance by name."""
        if not hasattr(self.clients.provided, client_name):
            available = [name for name in dir(self.clients.provided) if not name.startswith('_')]
            raise ValueError(f"Client '{client_name}' not found. Available: {available}")

        provider = getattr(self.clients.provided, client_name)
        return provider(**kwargs)

    def get_exporter(self, exporter_name: str, **kwargs: Any) -> Any:
        """Get exporter instance by name."""
        if not hasattr(self.exporters.provided, exporter_name):
            available = [name for name in dir(self.exporters.provided) if not name.startswith('_')]
            raise ValueError(f"Exporter '{exporter_name}' not found. Available: {available}")

        provider = getattr(self.exporters.provided, exporter_name)
        return provider(**kwargs)

    def list_available_services(self) -> Dict[str, List[str]]:
        """List all available services by category."""
        result = {}

        containers = {
            'services': self.services.provided,
            'clients': self.clients.provided,
            'exporters': self.exporters.provided,
            'processors': self.processors.provided,
            'ui': self.ui.provided,
            'composers': self.composers.provided,
            'service_managers': self.service_managers.provided,
        }

        for category, container in containers.items():
            available = [name for name in dir(container) if not name.startswith('_')]
            result[category] = available

        return result

    def configure_from_dict(self, config: Dict[str, Any]) -> None:
        """Configure container from dictionary."""
        self.config.from_dict(config)

        # Propagate config to child containers
        for container_attr in ['services', 'clients', 'exporters', 'processors', 'ui', 'composers', 'service_managers']:
            container = getattr(self, container_attr)
            if hasattr(container.provided, 'config'):
                container.provided.config.from_dict(config.get(container_attr, {}))

    def configure_from_yaml(self, yaml_path: str) -> None:
        """Configure container from YAML file."""
        self.config.from_yaml(yaml_path)

    def configure_from_env(self, prefix: str = "AIPERF") -> None:
        """Configure container from environment variables."""
        self.config.from_env(prefix)


# Create global application container instance (lazy initialization)
app_container = None

def get_app_container() -> ApplicationContainer:
    """Get or create the application container."""
    global app_container
    if app_container is None:
        app_container = ApplicationContainer()
    return app_container
