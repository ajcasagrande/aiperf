# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Protocol validation system for dependency injection.

This module provides runtime validation of protocol compliance and type checking
for the modern dependency injection system.
"""

import inspect
from typing import Any, Protocol, Type, get_type_hints, runtime_checkable
from collections.abc import Callable

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.exceptions import FactoryCreationError

logger = AIPerfLogger(__name__)


class ValidationError(Exception):
    """Raised when protocol validation fails."""
    pass


class ProtocolValidator:
    """Validates that classes implement protocols correctly."""

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: If True, raises exceptions on validation failures.
                        If False, only logs warnings.
        """
        self.strict_mode = strict_mode

    def validate_protocol_implementation(
        self,
        instance: Any,
        protocol: Type[Protocol],
        plugin_name: str = "unknown"
    ) -> bool:
        """
        Validate that an instance implements a protocol.

        Args:
            instance: The instance to validate
            protocol: The protocol to validate against
            plugin_name: Name of the plugin for error reporting

        Returns:
            True if validation passes, False otherwise

        Raises:
            ValidationError: If strict_mode is True and validation fails
        """
        if not self._is_protocol(protocol):
            logger.warning(f"'{protocol}' is not a Protocol, skipping validation")
            return True

        try:
            # Check if protocol is runtime_checkable
            if hasattr(protocol, '__protocol__') and getattr(protocol, '__runtime_checkable__', False):
                # Use isinstance for runtime checkable protocols
                if not isinstance(instance, protocol):
                    return self._handle_validation_failure(
                        f"Plugin '{plugin_name}' does not implement protocol '{protocol.__name__}' "
                        f"(failed isinstance check)"
                    )
            else:
                # Manual validation for non-runtime-checkable protocols
                if not self._validate_protocol_methods(instance, protocol):
                    return self._handle_validation_failure(
                        f"Plugin '{plugin_name}' does not implement all required methods "
                        f"from protocol '{protocol.__name__}'"
                    )

            # Validate method signatures
            if not self._validate_method_signatures(instance, protocol):
                return self._handle_validation_failure(
                    f"Plugin '{plugin_name}' has incompatible method signatures "
                    f"for protocol '{protocol.__name__}'"
                )

            logger.debug(f"Plugin '{plugin_name}' successfully validates against '{protocol.__name__}'")
            return True

        except Exception as e:
            return self._handle_validation_failure(
                f"Error validating plugin '{plugin_name}' against protocol '{protocol.__name__}': {e}"
            )

    def _is_protocol(self, cls: Type) -> bool:
        """Check if a class is a Protocol."""
        return (
            hasattr(cls, '__protocol__') or
            (hasattr(cls, '__mro__') and Protocol in cls.__mro__)
        )

    def _validate_protocol_methods(self, instance: Any, protocol: Type[Protocol]) -> bool:
        """Validate that instance has all required protocol methods."""
        protocol_methods = self._get_protocol_methods(protocol)
        instance_methods = self._get_instance_methods(instance)

        missing_methods = protocol_methods - instance_methods
        if missing_methods:
            logger.warning(
                f"Instance is missing protocol methods: {missing_methods}"
            )
            return False

        return True

    def _validate_method_signatures(self, instance: Any, protocol: Type[Protocol]) -> bool:
        """Validate method signatures match protocol requirements."""
        protocol_methods = self._get_protocol_method_signatures(protocol)

        for method_name, expected_sig in protocol_methods.items():
            if not hasattr(instance, method_name):
                continue  # Already caught by _validate_protocol_methods

            actual_method = getattr(instance, method_name)
            if not callable(actual_method):
                logger.warning(f"Protocol method '{method_name}' is not callable")
                return False

            try:
                actual_sig = inspect.signature(actual_method)
                if not self._signatures_compatible(actual_sig, expected_sig):
                    logger.warning(
                        f"Method '{method_name}' signature mismatch. "
                        f"Expected: {expected_sig}, Got: {actual_sig}"
                    )
                    return False
            except Exception as e:
                logger.warning(f"Could not validate signature for '{method_name}': {e}")

        return True

    def _get_protocol_methods(self, protocol: Type[Protocol]) -> set[str]:
        """Get set of method names defined in protocol."""
        methods = set()

        # Get methods from protocol annotations
        if hasattr(protocol, '__annotations__'):
            for name, annotation in protocol.__annotations__.items():
                if callable(annotation) or self._is_callable_annotation(annotation):
                    methods.add(name)

        # Get methods from protocol body
        for name in dir(protocol):
            if not name.startswith('_'):
                attr = getattr(protocol, name)
                if callable(attr) or self._is_abstract_method(attr):
                    methods.add(name)

        return methods

    def _get_instance_methods(self, instance: Any) -> set[str]:
        """Get set of callable method names from instance."""
        methods = set()
        for name in dir(instance):
            if not name.startswith('_'):
                attr = getattr(instance, name)
                if callable(attr):
                    methods.add(name)
        return methods

    def _get_protocol_method_signatures(self, protocol: Type[Protocol]) -> dict[str, inspect.Signature]:
        """Get method signatures from protocol."""
        signatures = {}

        for name in dir(protocol):
            if not name.startswith('_'):
                attr = getattr(protocol, name)
                if callable(attr):
                    try:
                        signatures[name] = inspect.signature(attr)
                    except (ValueError, TypeError):
                        # Some methods may not have inspectable signatures
                        pass

        return signatures

    def _is_callable_annotation(self, annotation: Any) -> bool:
        """Check if an annotation represents a callable."""
        return (
            hasattr(annotation, '__call__') or
            (hasattr(annotation, '__origin__') and
             annotation.__origin__ in (Callable, type(Callable)))
        )

    def _is_abstract_method(self, attr: Any) -> bool:
        """Check if an attribute is an abstract method."""
        return (
            hasattr(attr, '__isabstractmethod__') and
            attr.__isabstractmethod__
        )

    def _signatures_compatible(self, actual: inspect.Signature, expected: inspect.Signature) -> bool:
        """Check if two signatures are compatible."""
        # For now, do basic parameter count checking
        # This could be enhanced with more sophisticated type checking

        actual_params = [p for p in actual.parameters.values()
                        if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
        expected_params = [p for p in expected.parameters.values()
                          if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]

        # Allow for 'self' parameter differences
        if len(actual_params) > 0 and actual_params[0].name == 'self':
            actual_params = actual_params[1:]
        if len(expected_params) > 0 and expected_params[0].name == 'self':
            expected_params = expected_params[1:]

        return len(actual_params) == len(expected_params)

    def _handle_validation_failure(self, message: str) -> bool:
        """Handle validation failure based on strict_mode."""
        if self.strict_mode:
            raise ValidationError(message)
        else:
            logger.warning(message)
            return False


# Global validator instance
_validator = ProtocolValidator(strict_mode=False)


def set_validation_mode(strict: bool) -> None:
    """Set global validation mode."""
    global _validator
    _validator = ProtocolValidator(strict_mode=strict)


def validate_plugin(instance: Any, protocol: Type[Protocol], plugin_name: str = "unknown") -> bool:
    """Validate a plugin instance against a protocol."""
    return _validator.validate_protocol_implementation(instance, protocol, plugin_name)


def runtime_checkable_protocol(protocol_cls: Type[Protocol]) -> Type[Protocol]:
    """Decorator to make a protocol runtime checkable."""
    return runtime_checkable(protocol_cls)


# Enhanced protocol base classes with validation
@runtime_checkable
class ValidatedProtocol(Protocol):
    """Base protocol with built-in validation support."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Called when a class is subclassed."""
        super().__init_subclass__(**kwargs)
        # Mark as runtime checkable
        cls = runtime_checkable(cls)


# Validation decorators
def validate_implementation(protocol: Type[Protocol]):
    """Decorator to validate that a class implements a protocol."""
    def decorator(cls: Type) -> Type:
        # Add validation to __init__
        original_init = cls.__init__

        def validated_init(self, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            # Validate after initialization
            validate_plugin(self, protocol, cls.__name__)

        cls.__init__ = validated_init
        return cls

    return decorator


def require_protocol_compliance(protocol: Type[Protocol]):
    """Decorator for functions that require protocol-compliant arguments."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Validate first argument if it should implement the protocol
            if args and hasattr(protocol, '__protocol__'):
                validate_plugin(args[0], protocol, type(args[0]).__name__)
            return func(*args, **kwargs)
        return wrapper
    return decorator
