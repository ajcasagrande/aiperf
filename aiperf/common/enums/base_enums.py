# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Iterator
from enum import Enum
from typing import Any


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
        # TODO: Do we need to check if the value already exists in the enum?
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
                if ext_member.value == item:  # type: ignore
                    return True
            return False
        return item in cls.__members__ or item in cls._extensions.values()

    def __iter__(cls) -> Iterator["ExtensibleStrEnum"]:
        """Iterate over all enum members including extensions."""
        yield from cls.__members__.values()  # type: ignore
        yield from cls._extensions.values()  # type: ignore


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
        if hasattr(other, "value") and isinstance(other.value, str):  # type: ignore
            return self.value.lower() == other.value.lower()  # type: ignore
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
