# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from contextlib import suppress
from enum import Enum, EnumMeta
from typing import Union


class CaseInsensitiveStrEnum(str, Enum):
    """
    CaseInsensitiveStrEnum is a custom enumeration class that extends `str` and `Enum` to provide case-insensitive
    lookup functionality for its members.
    """

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.value.lower() == other.lower()
        if isinstance(other, Enum):
            return self.value.lower() == other.value.lower()
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value.lower())

    @classmethod
    def _missing_(cls, value):
        """
        Handles cases where a value is not directly found in the enumeration.

        This method is called when an attempt is made to access an enumeration
        member using a value that does not directly match any of the defined
        members. It provides custom logic to handle such cases.

        Returns:
            The matching enumeration member if a case-insensitive match is found
            for string values; otherwise, returns None.
        """
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None


class ExtensibleEnumMeta(EnumMeta):
    """
    Simplified metaclass for extensible enums that allows dynamic member registration.
    """

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # Use proper type annotation to avoid linter errors
        cls._extensions: dict[str, str] = {}
        return cls

    def __getattr__(cls, name: str):
        """Allow access to dynamically registered enum members."""
        if hasattr(cls, "_extensions") and name in cls._extensions:
            return cls._extensions[name]
        raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")

    def __dir__(cls):
        """Include dynamically registered members in dir() output for IDE support."""
        return list(super().__dir__()) + list(getattr(cls, "_extensions", {}).keys())


class ExtensibleEnum(str, Enum, metaclass=ExtensibleEnumMeta):
    """
    Base class for enums that can be extended with new values dynamically.

    This allows users to register new enum values from different packages
    while maintaining type safety and IDE support.

    Example:
        # Core definition
        class EndpointType(ExtensibleEnum):
            HTTP = "http"
            GRPC = "grpc"

        # User extension from another package
        EndpointType.register("WEBSOCKET", "websocket")
        EndpointType.register("CUSTOM", "custom")

        # Now users can access:
        endpoint = EndpointType.WEBSOCKET  # IDE recognizes this
        endpoint = EndpointType.CUSTOM     # IDE recognizes this
    """

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    @classmethod
    def register(cls, name: str, value: str) -> str:
        """
        Register a new enum value dynamically.

        Args:
            name: The attribute name for the new enum member
            value: The string value for the new enum member

        Returns:
            The registered value as a string

        Example:
            EndpointType.register("WEBSOCKET", "websocket")
            # Now EndpointType.WEBSOCKET is available
        """
        if name in cls.__members__:
            raise ValueError(f"'{name}' is already defined in {cls.__name__}")

        if name in cls._extensions:
            raise ValueError(
                f"'{name}' is already registered as an extension in {cls.__name__}"
            )

        # Store the value directly - much simpler than creating pseudo-enum objects
        cls._extensions[name] = value
        return value

    @classmethod
    def from_value(cls, value: str) -> Union["ExtensibleEnum", str]:
        """
        Create an enum member from a value, including extensions.

        This is the recommended way to create enum instances from string values
        when extensions might be involved, since Python's enum constructor
        doesn't work with extension members.

        Args:
            value: The string value to convert to an enum member

        Returns:
            The enum member (base or extension) matching the value

        Raises:
            ValueError: If the value is not found in base or extension members
        """
        with suppress(ValueError):
            return cls(value)

        for ext_value in cls._extensions.values():
            if ext_value == value:
                return ext_value

        raise ValueError(f"'{value}' is not a valid {cls.__name__}")

    @classmethod
    def get_all_values(cls) -> set[str]:
        """Get all enum values including extensions."""
        base_values = {member.value for member in cls.__members__.values()}
        extension_values = set(cls._extensions.values())
        return base_values | extension_values

    @classmethod
    def get_all_members(cls) -> dict[str, Union["ExtensibleEnum", str]]:
        """Get all enum members including extensions."""
        result: dict[str, ExtensibleEnum | str] = dict(cls.__members__)
        result.update(cls._extensions)
        return result

    @classmethod
    def get_base_members(cls) -> dict[str, "ExtensibleEnum"]:
        """Get only the originally defined enum members."""
        return dict(cls.__members__)

    @classmethod
    def get_extensions(cls) -> dict[str, str]:
        """Get only the dynamically registered extensions."""
        return dict(cls._extensions)

    @classmethod
    def find_member(cls, value: str) -> Union["ExtensibleEnum", str, None]:
        """Find an enum member by value, including extensions."""
        # Check base members first
        for member in cls.__members__.values():
            if member.value == value:
                return member

        # Check extensions
        for ext_value in cls._extensions.values():
            if ext_value == value:
                return ext_value

        return None

    @classmethod
    def is_valid_value(cls, value: str) -> bool:
        """Check if a value is valid for this enum, including extensions."""
        return value in cls.get_all_values()

    @classmethod
    def _missing_(cls, value):
        """Handle missing values - returns None to let normal enum error handling work."""
        # Don't try to return extension members here since Python's enum system
        # doesn't recognize them as valid. Use from_value() method instead.
        return None
