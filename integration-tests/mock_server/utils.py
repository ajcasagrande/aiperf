# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Utility functions for the mock server."""

import inspect


def supports_kwarg(obj: object, method_name: str, kwarg: str) -> bool:
    """Check if the given object has a method with the specified name
    that accepts a keyword argument with the specified name."""
    method = getattr(obj, method_name, None)
    if not method:
        return False
    return kwarg in inspect.signature(method).parameters
