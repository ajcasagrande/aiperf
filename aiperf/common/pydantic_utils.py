# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.types import BaseModelT


def exclude_if_none(field_names: list[str]):
    """Decorator to set the _exclude_if_none_fields class attribute to the set of
    field names that should be excluded if they are None.
    """

    def decorator(model: type[BaseModelT]) -> type[BaseModelT]:
        if not hasattr(model, "_exclude_if_none_fields"):
            model._exclude_if_none_fields = set()
        model._exclude_if_none_fields.update(field_names)
        return model

    return decorator
