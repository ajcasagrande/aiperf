#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Demonstration of type checking capabilities.

This script shows common type issues that mypy and other type checkers can catch.
Run with: python tools/type_demo.py
Check types with: mypy tools/type_demo.py
"""

import json
from pathlib import Path
from typing import Any


# ✅ Good: Properly typed function
def process_config(config_path: Path) -> dict[str, Any]:
    """Load and process configuration file."""
    with open(config_path) as f:
        return json.load(f)


# ❌ Type issue: Missing return type annotation
def calculate_average(numbers):
    """Calculate average of numbers."""
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


# ✅ Fixed version with proper types
def calculate_average_typed(numbers: list[float]) -> float | None:
    """Calculate average of numbers with proper typing."""
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


# ❌ Type issue: Inconsistent return types
def get_user_data(user_id: int):
    """Get user data - returns dict or string."""
    if user_id > 0:
        return {"id": user_id, "name": "User"}
    else:
        return "Invalid user ID"


# ✅ Fixed version with Union type
def get_user_data_typed(user_id: int) -> dict[str, Any] | str:
    """Get user data with proper Union typing."""
    if user_id > 0:
        return {"id": user_id, "name": "User"}
    else:
        return "Invalid user ID"


# ❌ Type issue: Using Any when more specific type is available
def process_items(items: Any) -> list[str]:
    """Process items into strings."""
    result = []
    for item in items:
        result.append(str(item))
    return result


# ✅ Fixed version with generic types
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def process_items_typed(items: Sequence[T]) -> list[str]:
    """Process items into strings with proper generics."""
    result = []
    for item in items:
        result.append(str(item))
    return result


# ❌ Type issue: Mutable default argument
def add_to_list(item: str, target_list: list[str] = []) -> list[str]:
    """Add item to list - DANGEROUS default argument!"""
    target_list.append(item)
    return target_list


# ✅ Fixed version with proper default
def add_to_list_typed(item: str, target_list: list[str] | None = None) -> list[str]:
    """Add item to list with safe default."""
    if target_list is None:
        target_list = []
    target_list.append(item)
    return target_list


class UserManager:
    """Example class with type issues and fixes."""

    def __init__(self):
        # ❌ Type issue: Untyped attribute
        self.users = {}

        # ✅ Better: Typed attribute
        self.active_sessions: dict[str, int] = {}

    # ❌ Type issue: Missing parameter and return types
    def create_user(self, name, email):
        user_id = len(self.users) + 1
        self.users[user_id] = {"name": name, "email": email}
        return user_id

    # ✅ Fixed version with proper types
    def create_user_typed(self, name: str, email: str) -> int:
        """Create user with proper typing."""
        user_id = len(self.users) + 1
        self.users[user_id] = {"name": name, "email": email}
        return user_id

    # ❌ Type issue: Could return None but not annotated
    def get_user(self, user_id: int):
        return self.users.get(user_id)

    # ✅ Fixed version with Optional
    def get_user_typed(self, user_id: int) -> dict[str, str] | None:
        """Get user with proper Optional typing."""
        return self.users.get(user_id)


def demonstrate_type_checking():
    """Demonstrate various type checking scenarios."""
    print("🔍 Type Checking Demonstration")
    print("=" * 50)

    # This will have type issues when checked with mypy
    manager = UserManager()

    # ❌ These calls will show type issues:
    user_id = manager.create_user(123, None)  # Wrong types
    user = manager.get_user("invalid")  # Wrong type

    # ❌ More type issues:
    numbers = [1, 2, "3", 4.5]  # Mixed types
    avg = calculate_average(numbers)  # Type checker can't verify

    # ❌ Dangerous mutable default:
    list1 = add_to_list("item1")
    list2 = add_to_list("item2")  # Will modify same list!

    print("✅ Script executed (but may have type issues)")
    print("🔧 Run 'mypy tools/type_demo.py' to see type errors")


if __name__ == "__main__":
    demonstrate_type_checking()
