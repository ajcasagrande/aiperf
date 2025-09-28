# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Custom providers for the AIPerf dependency injection system."""

import importlib.metadata
import threading
from typing import Any, Dict, Optional, Type, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol
else:
    try:
        from typing import Protocol
    except ImportError:
        from typing_extensions import Protocol
from collections.abc import Callable

from dependency_injector import providers
from pydantic import BaseModel, ValidationError

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.exceptions import FactoryCreationError

logger = AIPerfLogger(__name__)


@runtime_checkable
class PluginProtocol(Protocol):
    """Base protocol for all AIPerf plugins."""

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class LazyEntryPointProvider(providers.Provider):
    """Provider that lazily loads classes from entry points with full validation."""

    def __init__(
        self,
        entry_point_name: str,
        entry_point_group: str,
        expected_protocol: Optional[Type["Protocol"]] = None,
        config_model: Optional[Type[BaseModel]] = None,
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self._entry_point_name = entry_point_name
        self._entry_point_group = entry_point_group
        self._expected_protocol = expected_protocol
        self._config_model = config_model
        self._loaded_class: Optional[Type] = None
        self._load_lock = threading.Lock()

    def _provide(self, *args: Any, **kwargs: Any) -> Any:
        """Provide instance with lazy loading and validation."""
        if self._loaded_class is None:
            with self._load_lock:
                if self._loaded_class is None:
                    self._load_class()

        # Validate configuration if config model provided
        if self._config_model and kwargs:
            try:
                validated_config = self._config_model(**kwargs)
                kwargs = validated_config.model_dump()
            except ValidationError as e:
                raise FactoryCreationError(
                    f"Configuration validation failed for {self._entry_point_name}: {e}"
                ) from e

        try:
            instance = self._loaded_class(*args, **kwargs)
            self._validate_instance(instance)
            return instance
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create instance of {self._entry_point_name}: {e}"
            ) from e

    def _load_class(self) -> None:
        """Load class from entry point with validation."""
        try:
            entry_points = importlib.metadata.entry_points().select(
                group=self._entry_point_group,
                name=self._entry_point_name
            )

            entry_point = next(iter(entry_points), None)
            if entry_point is None:
                raise FactoryCreationError(
                    f"Entry point '{self._entry_point_name}' not found in group '{self._entry_point_group}'"
                )

            self._loaded_class = entry_point.load()
            logger.info(f"Loaded plugin: {self._entry_point_name} -> {self._loaded_class.__name__}")

            # Validate class implements expected protocol
            if self._expected_protocol:
                self._validate_class_protocol(self._loaded_class)

        except Exception as e:
            raise FactoryCreationError(
                f"Failed to load entry point '{self._entry_point_name}': {e}"
            ) from e

    def _validate_class_protocol(self, cls: Type) -> None:
        """Validate that class implements expected protocol."""
        if not self._expected_protocol:
            return

        # Check if protocol is runtime checkable
        if hasattr(self._expected_protocol, '__runtime_checkable__'):
            # Create a dummy instance for validation if possible
            try:
                # Try to validate without instantiation first
                if not issubclass(cls, self._expected_protocol):
                    logger.warning(
                        f"Class {cls.__name__} may not implement protocol {self._expected_protocol.__name__}"
                    )
            except TypeError:
                # Protocol is not a class, skip subclass check
                pass
        else:
            logger.debug(f"Protocol {self._expected_protocol.__name__} is not runtime checkable")

    def _validate_instance(self, instance: Any) -> None:
        """Validate instance implements expected protocol."""
        if not self._expected_protocol:
            return

        if hasattr(self._expected_protocol, '__runtime_checkable__'):
            if not isinstance(instance, self._expected_protocol):
                logger.warning(
                    f"Instance {type(instance).__name__} does not implement protocol {self._expected_protocol.__name__}"
                )


class ValidatedProvider(providers.Provider):
    """Provider that validates instances against protocols and configurations."""

    def __init__(
        self,
        provides: Type,
        expected_protocol: Optional[Type["Protocol"]] = None,
        config_model: Optional[Type[BaseModel]] = None,
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self._provides = provides
        self._expected_protocol = expected_protocol
        self._config_model = config_model

    def _provide(self, *args: Any, **kwargs: Any) -> Any:
        """Provide validated instance."""
        # Validate configuration
        if self._config_model and kwargs:
            try:
                validated_config = self._config_model(**kwargs)
                kwargs = validated_config.model_dump()
            except ValidationError as e:
                raise FactoryCreationError(
                    f"Configuration validation failed: {e}"
                ) from e

        # Create instance
        try:
            instance = self._provides(*args, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create instance of {self._provides.__name__}: {e}"
            ) from e

        # Validate protocol compliance
        if self._expected_protocol and hasattr(self._expected_protocol, '__runtime_checkable__'):
            if not isinstance(instance, self._expected_protocol):
                logger.warning(
                    f"Instance {type(instance).__name__} does not implement protocol {self._expected_protocol.__name__}"
                )

        return instance


class ConfigurableProvider(providers.Provider):
    """Provider that supports configuration from external sources."""

    def __init__(
        self,
        provides: Type,
        config_key: str,
        config_model: Optional[Type[BaseModel]] = None,
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self._provides = provides
        self._config_key = config_key
        self._config_model = config_model
        self._config_cache: Dict[str, Any] = {}

    def _provide(self, config_source: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Provide instance with configuration support."""
        # Get configuration from source
        config = {}
        if config_source and self._config_key in config_source:
            config = config_source[self._config_key]

        # Merge with provided kwargs
        config.update(kwargs)

        # Validate configuration
        if self._config_model:
            try:
                validated_config = self._config_model(**config)
                config = validated_config.model_dump()
            except ValidationError as e:
                raise FactoryCreationError(
                    f"Configuration validation failed for {self._config_key}: {e}"
                ) from e

        # Create instance
        try:
            return self._provides(**config)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create configured instance of {self._provides.__name__}: {e}"
            ) from e


class SingletonProvider(providers.Singleton):
    """Enhanced singleton provider with validation and configuration."""

    def __init__(
        self,
        provides: Type,
        expected_protocol: Optional[Type["Protocol"]] = None,
        config_model: Optional[Type[BaseModel]] = None,
        **kwargs: Any
    ):
        super().__init__(provides, **kwargs)
        self._expected_protocol = expected_protocol
        self._config_model = config_model

    def _provide(self, *args: Any, **kwargs: Any) -> Any:
        """Provide singleton instance with validation."""
        # Validate configuration
        if self._config_model and kwargs:
            try:
                validated_config = self._config_model(**kwargs)
                kwargs = validated_config.model_dump()
            except ValidationError as e:
                raise FactoryCreationError(
                    f"Configuration validation failed: {e}"
                ) from e

        # Get or create singleton instance
        instance = super()._provide(*args, **kwargs)

        # Validate protocol compliance (only on first creation)
        if (self._expected_protocol and
            hasattr(self._expected_protocol, '__runtime_checkable__') and
            not isinstance(instance, self._expected_protocol)):
            logger.warning(
                f"Singleton instance {type(instance).__name__} does not implement protocol {self._expected_protocol.__name__}"
            )

        return instance


class FactoryProvider(providers.Factory):
    """Enhanced factory provider with validation and configuration."""

    def __init__(
        self,
        provides: Type,
        expected_protocol: Optional[Type["Protocol"]] = None,
        config_model: Optional[Type[BaseModel]] = None,
        **kwargs: Any
    ):
        super().__init__(provides, **kwargs)
        self._expected_protocol = expected_protocol
        self._config_model = config_model

    def _provide(self, *args: Any, **kwargs: Any) -> Any:
        """Provide factory instance with validation."""
        # Validate configuration
        if self._config_model and kwargs:
            try:
                validated_config = self._config_model(**kwargs)
                kwargs = validated_config.model_dump()
            except ValidationError as e:
                raise FactoryCreationError(
                    f"Configuration validation failed: {e}"
                ) from e

        # Create instance
        instance = super()._provide(*args, **kwargs)

        # Validate protocol compliance
        if (self._expected_protocol and
            hasattr(self._expected_protocol, '__runtime_checkable__') and
            not isinstance(instance, self._expected_protocol)):
            logger.warning(
                f"Factory instance {type(instance).__name__} does not implement protocol {self._expected_protocol.__name__}"
            )

        return instance


def create_lazy_provider(
    entry_point_name: str,
    entry_point_group: str,
    provider_type: str = "factory",
    expected_protocol: Optional[Type["Protocol"]] = None,
    config_model: Optional[Type[BaseModel]] = None
) -> providers.Provider:
    """Factory function to create appropriate lazy provider."""

    if provider_type == "singleton":
        # For singleton, we need to wrap LazyEntryPointProvider in Singleton
        class LazySingletonProvider(providers.Singleton):
            def __init__(self):
                self._lazy_provider = LazyEntryPointProvider(
                    entry_point_name=entry_point_name,
                    entry_point_group=entry_point_group,
                    expected_protocol=expected_protocol,
                    config_model=config_model
                )
                super().__init__(self._lazy_provider._provide)

        return LazySingletonProvider()

    else:
        return LazyEntryPointProvider(
            entry_point_name=entry_point_name,
            entry_point_group=entry_point_group,
            expected_protocol=expected_protocol,
            config_model=config_model
        )
