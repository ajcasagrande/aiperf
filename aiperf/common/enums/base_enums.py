# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Iterator
from enum import Enum
from functools import cached_property

from pydantic import BaseModel, Field
from typing_extensions import Self


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
    def itervalues(cls) -> Iterator[Self]:
        return iter(member for member in cls.__members__.values())

    @classmethod
    def _missing_(cls, value):
        """
        Handles cases where a value is not directly found in the enumeration.

        This method is called when an attempt is made to access an enumeration
        member using a value that does not directly match any of the defined
        members. It provides custom logic to handle such cases. It is also insensitive
        to underscores versus dashes in the value.

        Returns:
            The matching enumeration member if a case-insensitive match is found
            for string values; otherwise, returns None.
        """
        if isinstance(value, str):
            for member in cls:
                if member.value.lower().replace("_", "-") == value.lower().replace(
                    "_", "-"
                ):
                    return member
        return None


class BasePydanticEnumInfo(BaseModel):
    """Base class for all enum info classes that extend `BasePydanticBackedStrEnum`. By default, it
    provides a `tag` for the enum member, which is used for lookup and string comparison,
    and the subclass can provide additional information as needed."""

    tag: str = Field(
        ...,
        min_length=1,
        description="The string value of the enum member used for lookup, serialization, and string insensitive comparison.",
    )

    def __str__(self) -> str:
        return self.tag


class BasePydanticBackedStrEnum(CaseInsensitiveStrEnum):
    """
    Custom enumeration class that extends `CaseInsensitiveStrEnum`
    and is backed by a `BasePydanticEnumInfo` that contains the `tag`, and any other information that is needed
    to represent the enum member.
    """

    # Override the __new__ method to store the `BasePydanticEnumInfo` subclass model as an attribute. This is a python feature that
    # allows us to modify the behavior of the enum class's constructor. We use this to ensure the the enums still look like
    # a regular string enum, but also have the additional information stored as an attribute.
    def __new__(cls, info: BasePydanticEnumInfo) -> Self:
        # Create a new string object based on this class and the tag value.
        obj = str.__new__(cls, info.tag)
        # Ensure string value is set for comparison. This is how enums work internally.
        obj._value_ = info.tag
        # Store the Pydantic model as an attribute.
        obj._info: BasePydanticEnumInfo = info  # type: ignore
        return obj

    @cached_property
    def info(self) -> BasePydanticEnumInfo:
        """Get the enum info for the enum member."""
        # This is the Pydantic model that was stored as an attribute in the __new__ method.
        return self._info  # type: ignore


# class ExtensibleStrEnumMeta(type(Enum)):
#     """Metaclass for extensible enums."""

#     def __new__(mcs, name, bases, namespace, **kwargs):
#         cls = super().__new__(mcs, name, bases, namespace, **kwargs)
#         cls._extensions: dict[str, ExtensibleStrEnum] = {}  # type: ignore
#         return cls

#     def __getattr__(cls, name: str) -> "ExtensibleStrEnum":
#         """Allow access to dynamically registered enum members."""
#         if hasattr(cls, "_extensions") and name in cls._extensions:
#             return cls._extensions[name]  # type: ignore
#         raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")

#     def __dir__(cls):
#         """Include dynamically registered members in dir() output for IDE support."""
#         return list(super().__dir__()) + list(getattr(cls, "_extensions", {}).keys())

#     def __contains__(cls, item: object) -> bool:
#         if isinstance(item, str):
#             # Check if the string value exists in base members or extensions
#             for member in cls.__members__.values():
#                 if member.value == item:
#                     return True
#             for ext_member in cls._extensions.values():
#                 if ext_member.value == item:
#                     return True
#             return False
#         return item in cls.__members__ or item in cls._extensions.values()

#     def __iter__(cls) -> Iterator["ExtensibleStrEnum"]:
#         """Iterate over all enum members including extensions."""
#         yield from cls.__members__.values()
#         yield from cls._extensions.values()

#     def __getitem__(cls, item: str) -> "ExtensibleStrEnum":
#         """Get enum member by name."""
#         if item in cls.__members__:
#             return cls.__members__[item]
#         if item in cls._extensions:
#             return cls._extensions[item]
#         raise KeyError(f"'{item}' is not a valid {cls.__name__} member")

#     def values(cls) -> set[str]:
#         """Get all enum values including extensions."""
#         base_members = set(cls.__members__.values())
#         extension_members = set(cls._extensions.values())
#         return base_members | extension_members

#     def names(cls) -> set[str]:
#         """Get all enum names including extensions."""
#         base_names = set(cls.__members__.keys())
#         extension_names = set(cls._extensions.keys())
#         return base_names | extension_names

#     def __len__(cls) -> int:
#         return len(cls.__members__) + len(cls._extensions)

#     def _missing_(cls, value: object) -> "ExtensibleStrEnum | None":
#         """Handle case-insensitive lookups for string values."""
#         if isinstance(value, str):
#             for member in cls.__members__.values():
#                 if member.value.lower() == value.lower():
#                     return member

#             for ext_member in cls._extensions.values():
#                 if ext_member.value.lower() == value.lower():
#                     return ext_member
#         return None


# class ExtensibleStrEnum(str, Enum, metaclass=ExtensibleStrEnumMeta):
#     """Extensible enum that can be extended with new values dynamically."""

#     _extensions: dict[str, "ExtensibleStrEnum"]

#     def __str__(self) -> str:
#         return self.value

#     def __repr__(self) -> str:
#         return f"{self.__class__.__name__}.{self.name}"

#     def __eq__(self, other: object) -> bool:
#         if isinstance(other, str):
#             return self.value.lower() == other.lower()
#         if hasattr(other, "value") and isinstance(other.value, str):
#             return self.value.lower() == other.value.lower()
#         return super().__eq__(other)

#     def __hash__(self) -> int:
#         return hash(self.value.lower())

#     @property
#     def name(self) -> str:
#         if hasattr(self, "_name_"):
#             return self._name_
#         return super().name

#     @property
#     def value(self) -> str:
#         if hasattr(self, "_value_"):
#             return self._value_
#         return super().value

#     @classmethod
#     def register(cls, name: str, value: str) -> "ExtensibleStrEnum":
#         """Register a new enum member dynamically."""
#         if name in cls.__members__:
#             raise ValueError(f"'{name}' is already defined in {cls.__name__}")

#         if name in cls._extensions:
#             raise ValueError(
#                 f"'{name}' is already registered as an extension in {cls.__name__}"
#             )

#         extension_member = cls._create_extension_member(name, value)
#         cls._extensions[name] = extension_member
#         return extension_member

#     @classmethod
#     def _create_extension_member(cls, name: str, value: str) -> "ExtensibleStrEnum":
#         """Create an extension member that behaves like a real enum member."""
#         obj = str.__new__(cls, value)
#         obj._name_ = name
#         obj._value_ = value
#         obj.__class__ = cls
#         return obj

#     @classmethod
#     def values(cls) -> list[str]:
#         """Get all string values including extensions."""
#         base_values = [member.value for member in cls.__members__.values()]
#         extension_values = [member.value for member in cls._extensions.values()]
#         return base_values + extension_values

#     @classmethod
#     def names(cls) -> list[str]:
#         """Get all member names including extensions."""
#         base_names = list(cls.__members__.keys())
#         extension_names = list(cls._extensions.keys())
#         return base_names + extension_names

#     @classmethod
#     def _missing_(cls, value):
#         """Handle case-insensitive lookups."""
#         if isinstance(value, str):
#             # Check base members
#             for member in cls.__members__.values():
#                 if member.value.lower() == value.lower():
#                     return member
#             # Check extensions
#             for ext_member in cls._extensions.values():
#                 if ext_member.value.lower() == value.lower():
#                     return ext_member
#         return None


# class EndpointType(ExtensibleStrEnum):
#     HTTP = "http"
#     GRPC = "grpc"


# if __name__ == "__main__":
#     print("=== Enhanced ExtensibleEnum Test ===")

#     print("Original members:")
#     for member in EndpointType:
#         print(f"  {type(member).__name__}: {member.name} = {member.value}")

#     # Register extensions
#     websocket = EndpointType.register("WEBSOCKET", "websocket")
#     custom = EndpointType.register("CUSTOM", "custom")

#     print(f"\nAll values: {EndpointType.values()}")
#     print(f"All names: {EndpointType.names()}")

#     # Test access methods
#     print(f"\nBase enum member: {EndpointType.HTTP}")
#     print(f"Extension via attribute: {EndpointType.WEBSOCKET}")
#     print(f"Extension via variable: {websocket}")

#     # Test from_value method
#     print(f"\nfrom_value('http'): {EndpointType('http')}")
#     print(f"from_value('websocket'): {EndpointType('websocket')}")

#     # Test validation
#     print("\nValidation:")
#     print(f"'http' in EndpointType: {'http' in EndpointType}")
#     print(f"'websocket' in EndpointType: {'websocket' in EndpointType}")
#     print(f"'invalid' in EndpointType: {'invalid' in EndpointType}")

#     # Test string comparisons
#     endpoint1 = EndpointType.HTTP
#     endpoint2 = EndpointType.WEBSOCKET

#     print("\nString comparisons:")
#     print(f"EndpointType.HTTP == 'http': {endpoint1 == 'http'}")
#     print(f"EndpointType.WEBSOCKET == 'websocket': {endpoint2 == 'websocket'}")

#     # Show type information - THIS IS THE KEY TEST
#     print("\nType information:")
#     print(f"type(EndpointType.HTTP): {type(endpoint1)}")
#     print(f"type(EndpointType.WEBSOCKET): {type(endpoint2)}")
#     print(f"EndpointType.HTTP.__class__.__name__: {endpoint1.__class__.__name__}")
#     print(f"EndpointType.WEBSOCKET.__class__.__name__: {endpoint2.__class__.__name__}")

#     # Test isinstance checks
#     print("\nInstance checks:")
#     print(
#         f"isinstance(EndpointType.HTTP, EndpointType): {isinstance(endpoint1, EndpointType)}"
#     )
#     print(
#         f"isinstance(EndpointType.WEBSOCKET, EndpointType): {isinstance(endpoint2, EndpointType)}"
#     )
#     print(f"isinstance(EndpointType.HTTP, str): {isinstance(endpoint1, str)}")
#     print(f"isinstance(EndpointType.WEBSOCKET, str): {isinstance(endpoint2, str)}")

#     # Test enum properties
#     print("\nEnum properties:")
#     print(f"EndpointType.HTTP.name: {endpoint1.name}")
#     print(f"EndpointType.HTTP.value: {endpoint1.value}")
#     print(f"EndpointType.WEBSOCKET.name: {endpoint2.name}")
#     print(f"EndpointType.WEBSOCKET.value: {endpoint2.value}")

#     print(EndpointType("websocket"))
#     print(EndpointType("websocket").__class__)
#     for member in EndpointType:
#         print(repr(member))
