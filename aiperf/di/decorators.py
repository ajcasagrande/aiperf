# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Dependency injection decorators and utilities."""

import functools
import inspect
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union
from collections.abc import Awaitable

from dependency_injector.wiring import Provide, inject as di_inject
from pydantic import BaseModel

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import ServiceType
from aiperf.di.containers import app_container

logger = AIPerfLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def inject_service(
    service_name: Union[str, ServiceType],
    parameter_name: Optional[str] = None,
    **service_kwargs: Any
) -> Callable[[F], F]:
    """Inject a service into a function or method.

    Args:
        service_name: Name of the service to inject (enum or string)
        parameter_name: Name of the parameter to inject into (defaults to first parameter)
        **service_kwargs: Additional kwargs to pass to service constructor

    Example:
        @inject_service(ServiceType.WORKER, worker_count=4)
        def process_data(worker_service, data: str):
            return worker_service.process(data)
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get service name as string
            svc_name = service_name.value if hasattr(service_name, 'value') else str(service_name)

            try:
                # Get service instance
                service = app_container.get_service(svc_name, **service_kwargs)

                # Determine parameter name
                if parameter_name:
                    kwargs[parameter_name] = service
                else:
                    # Inject as first positional argument
                    args = (service,) + args

                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Failed to inject service '{svc_name}': {e}")
                raise

        return wrapper
    return decorator


def inject_client(
    client_name: str,
    parameter_name: Optional[str] = None,
    **client_kwargs: Any
) -> Callable[[F], F]:
    """Inject a client into a function or method."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                client = app_container.get_client(client_name, **client_kwargs)

                if parameter_name:
                    kwargs[parameter_name] = client
                else:
                    args = (client,) + args

                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Failed to inject client '{client_name}': {e}")
                raise

        return wrapper
    return decorator


def inject_exporter(
    exporter_name: str,
    parameter_name: Optional[str] = None,
    **exporter_kwargs: Any
) -> Callable[[F], F]:
    """Inject an exporter into a function or method."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                exporter = app_container.get_exporter(exporter_name, **exporter_kwargs)

                if parameter_name:
                    kwargs[parameter_name] = exporter
                else:
                    args = (exporter,) + args

                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Failed to inject exporter '{exporter_name}': {e}")
                raise

        return wrapper
    return decorator


def auto_wire(
    container_attr: str = "services",
    service_mapping: Optional[Dict[str, str]] = None
) -> Callable[[F], F]:
    """Automatically wire dependencies based on function signature.

    Args:
        container_attr: Which container to use (services, clients, exporters, etc.)
        service_mapping: Optional mapping of parameter names to service names

    Example:
        @auto_wire(service_mapping={'worker': 'worker_service', 'db': 'database_client'})
        def process_data(worker, db, data: str):
            # worker and db are automatically injected
            pass
    """
    def decorator(func: F) -> F:
        # Analyze function signature
        sig = inspect.signature(func)
        injectable_params = []

        for param_name, param in sig.parameters.items():
            # Skip self, cls, args, kwargs
            if param_name in ('self', 'cls') or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # Check if parameter should be injected
            service_name = None
            if service_mapping and param_name in service_mapping:
                service_name = service_mapping[param_name]
            elif param.annotation and hasattr(param.annotation, '__name__'):
                # Try to infer service name from type annotation
                service_name = param.annotation.__name__.lower()

            if service_name:
                injectable_params.append((param_name, service_name))

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            container = getattr(app_container, container_attr)

            # Inject dependencies
            for param_name, service_name in injectable_params:
                if param_name not in kwargs:
                    try:
                        if container_attr == "services":
                            service = app_container.get_service(service_name)
                        elif container_attr == "clients":
                            service = app_container.get_client(service_name)
                        elif container_attr == "exporters":
                            service = app_container.get_exporter(service_name)
                        else:
                            # Generic container access
                            if hasattr(container.provided, service_name):
                                provider = getattr(container.provided, service_name)
                                service = provider()
                            else:
                                logger.warning(f"Service '{service_name}' not found in {container_attr}")
                                continue

                        kwargs[param_name] = service

                    except Exception as e:
                        logger.error(f"Failed to auto-wire '{param_name}' -> '{service_name}': {e}")

            return func(*args, **kwargs)

        return wrapper
    return decorator


def async_inject_service(
    service_name: Union[str, ServiceType],
    parameter_name: Optional[str] = None,
    **service_kwargs: Any
) -> Callable[[F], F]:
    """Async version of inject_service decorator."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            svc_name = service_name.value if hasattr(service_name, 'value') else str(service_name)

            try:
                service = app_container.get_service(svc_name, **service_kwargs)

                if parameter_name:
                    kwargs[parameter_name] = service
                else:
                    args = (service,) + args

                result = func(*args, **kwargs)
                if inspect.iscoroutine(result):
                    return await result
                return result

            except Exception as e:
                logger.error(f"Failed to inject service '{svc_name}': {e}")
                raise

        return wrapper
    return decorator


def inject_config(
    config_key: str,
    parameter_name: Optional[str] = None,
    config_model: Optional[Type[BaseModel]] = None
) -> Callable[[F], F]:
    """Inject configuration into a function or method.

    Args:
        config_key: Key in the configuration
        parameter_name: Parameter name to inject into
        config_model: Optional Pydantic model for validation
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Get config from application container
                config_value = app_container.config.get(config_key)

                # Validate with Pydantic model if provided
                if config_model and config_value:
                    config_value = config_model(**config_value).model_dump()

                if parameter_name:
                    kwargs[parameter_name] = config_value
                else:
                    args = (config_value,) + args

                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Failed to inject config '{config_key}': {e}")
                raise

        return wrapper
    return decorator


def requires_services(*service_names: Union[str, ServiceType]) -> Callable[[F], F]:
    """Decorator to validate that required services are available.

    Args:
        *service_names: Names of required services

    Example:
        @requires_services(ServiceType.WORKER, ServiceType.DATABASE)
        def complex_operation():
            # This will only run if both services are available
            pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check service availability
            missing_services = []

            for service_name in service_names:
                svc_name = service_name.value if hasattr(service_name, 'value') else str(service_name)
                try:
                    app_container.get_service(svc_name)
                except Exception:
                    missing_services.append(svc_name)

            if missing_services:
                raise RuntimeError(f"Required services not available: {missing_services}")

            return func(*args, **kwargs)

        return wrapper
    return decorator


def service_factory(service_type: Union[str, ServiceType]):
    """Create a service factory function.

    Args:
        service_type: Type of service to create

    Returns:
        Factory function that creates service instances

    Example:
        create_worker = service_factory(ServiceType.WORKER)
        worker = create_worker(worker_count=4)
    """
    svc_name = service_type.value if hasattr(service_type, 'value') else str(service_type)

    def factory(**kwargs: Any) -> Any:
        return app_container.get_service(svc_name, **kwargs)

    factory.__name__ = f"create_{svc_name}"
    factory.__doc__ = f"Create {svc_name} service instance"

    return factory


# Convenience factory functions
create_service = lambda name, **kwargs: app_container.get_service(name, **kwargs)
create_client = lambda name, **kwargs: app_container.get_client(name, **kwargs)
create_exporter = lambda name, **kwargs: app_container.get_exporter(name, **kwargs)
