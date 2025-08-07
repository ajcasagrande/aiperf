# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from functools import lru_cache
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_serializer

from aiperf.common.types import AIPerfBaseModelT


@lru_cache(maxsize=256)
def _get_exclude_fields(
    exclude_fields: frozenset[str], model_data: tuple
) -> dict[str, Any]:
    """Cached filtering of fields to exclude when they are None.

    Args:
        exclude_fields: Frozen set of field names to exclude if None
        model_data: Tuple of (key, value) pairs from model

    Returns:
        Filtered dictionary with None fields excluded
    """
    return {k: v for k, v in model_data if not (k in exclude_fields and v is None)}


def exclude_if_none(*field_names: str):
    """Decorator to set the _exclude_if_none_fields class attribute to the set of
    field names that should be excluded if they are None.

    Optimized to use frozenset for better performance.
    """

    def decorator(model: type[AIPerfBaseModelT]) -> type[AIPerfBaseModelT]:
        # This attribute is defined by the AIPerfBaseModel class.
        if not hasattr(model, "_exclude_if_none_fields"):
            model._exclude_if_none_fields = frozenset()
        else:
            # Convert existing set to frozenset if needed
            if isinstance(model._exclude_if_none_fields, set):
                model._exclude_if_none_fields = frozenset(model._exclude_if_none_fields)

        # Update with new field names, keeping as frozenset
        model._exclude_if_none_fields = model._exclude_if_none_fields | frozenset(
            field_names
        )
        return model

    return decorator


class AIPerfBaseModel(BaseModel):
    """Base model for all AIPerf Pydantic models. This class is configured to allow
    arbitrary types to be used as fields as to allow for more flexible model definitions
    by end users without breaking the existing code.

    The @exclude_if_none decorator can also be used to specify which fields
    should be excluded from the serialized model if they are None. This is a workaround
    for the fact that pydantic does not support specifying exclude_none on a per-field basis.

    Optimized for high-performance serialization with caching.
    """

    _exclude_if_none_fields: ClassVar[frozenset[str]] = frozenset()
    """Set of field names that should be excluded from the serialized model if they
    are None. This is set by the @exclude_if_none decorator.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        # Performance optimizations
        validate_assignment=False,  # Skip validation on assignment for better performance
        use_enum_values=True,  # Use enum values directly
        str_strip_whitespace=True,  # Strip whitespace for strings
    )

    @model_serializer
    def _serialize_model(self) -> dict[str, Any]:
        """Serialize the model to a dictionary.

        This method overrides the default serializer to exclude fields that with a
        value of None and were marked with the @exclude_if_none decorator.

        Optimized version using caching.
        """
        if not self._exclude_if_none_fields:
            # Fast path: no fields to exclude
            return dict(self)

        # Convert model data to hashable tuple for caching
        model_items = tuple(self)

        # Use cached filtering function
        return _get_exclude_fields(self._exclude_if_none_fields, model_items)
