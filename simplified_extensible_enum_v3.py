# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Iterator
from enum import Enum
from typing import Any


class ExtensibleStrEnumMeta(type(Enum)):
    """Metaclass for extensible enums."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        cls._extensions = {}
        return cls

    def __getattr__(cls, name: str) -> "ExtensibleStrEnum":
        """Allows access to dynamically registered enum members."""
        if "_extensions" in cls.__dict__ and name in cls.__dict__["_extensions"]:
            return cls.__dict__["_extensions"][name]
        raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")

    def __setattr__(cls, name: str, value: Any) -> None:
        """Allows setting new enum members dynamically."""
        if name.startswith("_") or "_extensions" not in cls.__dict__:
            return super().__setattr__(name, value)
        if name in cls.__members__:
            raise ValueError(f"'{name}' is already defined in {cls.__name__}")
        if name in cls.__dict__["_extensions"]:
            raise ValueError(
                f"'{name}' is already registered as an extension in {cls.__name__}"
            )
        cls.__dict__["_extensions"][name] = cls._create_extension_member(name, value)
        return cls.__dict__["_extensions"][name]

    def _create_extension_member(cls, name: str, value: str) -> "ExtensibleStrEnum":
        """Creates an extension member that behaves like a real enum member."""
        obj = str.__new__(cls, value)  # type: ignore
        obj._name_ = name
        obj._value_ = value
        obj.__class__ = cls
        return obj

    def __dir__(cls):
        """Includes dynamically registered members in dir() output for IDE support."""
        return list(super().__dir__()) + list(getattr(cls, "_extensions", {}).keys())

    def __contains__(cls, item: object) -> bool:
        if isinstance(item, str):
            # Check if the string value exists in base members or extensions
            for member in cls.__members__.values():
                if member.value == item:
                    return True
            for ext_member in cls._extensions.values():
                if ext_member.value == item:
                    return True
            return False
        return item in cls.__members__ or item in cls._extensions.values()

    def __iter__(cls) -> Iterator["ExtensibleStrEnum"]:
        """Iterate over all enum members including extensions."""
        yield from cls.__members__.values()
        yield from cls._extensions.values()


class ExtensibleStrEnum(str, Enum, metaclass=ExtensibleStrEnumMeta):
    """Extensible enum that can be extended with new values dynamically."""

    _extensions: dict[str, "ExtensibleStrEnum"]

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.value.lower() == other.lower()
        if hasattr(other, "value") and isinstance(other.value, str):
            return self.value.lower() == other.value.lower()
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value.lower())

    @property
    def name(self) -> str:
        if hasattr(self, "_name_"):
            return self._name_
        return super().name

    @property
    def value(self) -> str:
        if hasattr(self, "_value_"):
            return self._value_
        return super().value

    @classmethod
    def register(cls, name: str, value: str) -> "ExtensibleStrEnum":
        """Register a new enum member dynamically."""
        if name in cls.__members__:
            raise ValueError(f"'{name}' is already defined in {cls.__name__}")

        if name in cls._extensions:
            raise ValueError(
                f"'{name}' is already registered as an extension in {cls.__name__}"
            )

        extension_member = cls._create_extension_member(name, value)
        cls._extensions[name] = extension_member
        return extension_member

    @classmethod
    def values(cls) -> list[str]:
        """Get all string values including extensions."""
        base_values = [member.value for member in cls.__members__.values()]
        extension_values = [member.value for member in cls._extensions.values()]
        return base_values + extension_values

    @classmethod
    def names(cls) -> list[str]:
        """Get all member names including extensions."""
        base_names = list(cls.__members__.keys())
        extension_names = list(cls._extensions.keys())
        return base_names + extension_names

    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive lookups."""
        if isinstance(value, str):
            # Check base members
            for member in cls.__members__.values():
                if member.value.lower() == value.lower():
                    return member
            # Check extensions
            for ext_member in cls._extensions.values():
                if ext_member.value.lower() == value.lower():
                    return ext_member
        return None


class EndpointType(ExtensibleStrEnum):
    HTTP = "http"
    GRPC = "grpc"


if __name__ == "__main__":
    print("=== Enhanced ExtensibleEnum Test ===")

    print("Original members:")
    for member in EndpointType:
        print(f"  {type(member).__name__}: {member.name} = {member.value}")

    EndpointType.WEBSOCKET2 = "websocket2"
    # EndpointType.WEBSOCKET = "websocket4"
    print(EndpointType.WEBSOCKET2)
    print(type(EndpointType.WEBSOCKET2))

    # Register extensions
    websocket = EndpointType.register("WEBSOCKET", "websocket")
    custom = EndpointType.register("CUSTOM", "custom")

    print(f"\nAll values: {EndpointType.values()}")
    print(f"All names: {EndpointType.names()}")

    # Test access methods
    print(f"\nBase enum member: {EndpointType.HTTP}")
    print(f"Extension via attribute: {EndpointType.WEBSOCKET}")
    print(f"Extension via variable: {websocket}")

    # Test from_value method
    print(f"\nfrom_value('http'): {EndpointType('http')}")
    print(f"from_value('websocket'): {EndpointType('websocket')}")

    # Test validation
    print("\nValidation:")
    print(f"'http' in EndpointType: {'http' in EndpointType}")
    print(f"'websocket' in EndpointType: {'websocket' in EndpointType}")
    print(f"'invalid' in EndpointType: {'invalid' in EndpointType}")

    # Test string comparisons
    endpoint1 = EndpointType.HTTP
    endpoint2 = EndpointType.WEBSOCKET

    print("\nString comparisons:")
    print(f"EndpointType.HTTP == 'http': {endpoint1 == 'http'}")
    print(f"EndpointType.WEBSOCKET == 'websocket': {endpoint2 == 'websocket'}")

    # Show type information - THIS IS THE KEY TEST
    print("\nType information:")
    print(f"type(EndpointType.HTTP): {type(endpoint1)}")
    print(f"type(EndpointType.WEBSOCKET): {type(endpoint2)}")
    print(f"EndpointType.HTTP.__class__.__name__: {endpoint1.__class__.__name__}")
    print(f"EndpointType.WEBSOCKET.__class__.__name__: {endpoint2.__class__.__name__}")

    # Test isinstance checks
    print("\nInstance checks:")
    print(
        f"isinstance(EndpointType.HTTP, EndpointType): {isinstance(endpoint1, EndpointType)}"
    )
    print(
        f"isinstance(EndpointType.WEBSOCKET, EndpointType): {isinstance(endpoint2, EndpointType)}"
    )
    print(f"isinstance(EndpointType.HTTP, str): {isinstance(endpoint1, str)}")
    print(f"isinstance(EndpointType.WEBSOCKET, str): {isinstance(endpoint2, str)}")

    # Test enum properties
    print("\nEnum properties:")
    print(f"EndpointType.HTTP.name: {endpoint1.name}")
    print(f"EndpointType.HTTP.value: {endpoint1.value}")
    print(f"EndpointType.WEBSOCKET.name: {endpoint2.name}")
    print(f"EndpointType.WEBSOCKET.value: {endpoint2.value}")

    print(EndpointType("websocket"))
    print(EndpointType("websocket").__class__)
    for member in EndpointType:
        print(repr(member))
