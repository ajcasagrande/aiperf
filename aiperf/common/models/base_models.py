# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_serializer

from aiperf.common.types import AIPerfBaseModelT


def exclude_if_none(*field_names: str):
    """Decorator to set the _exclude_if_none_fields class attribute to the set of
    field names that should be excluded if they are None.
    """

    def decorator(model: type[AIPerfBaseModelT]) -> type[AIPerfBaseModelT]:
        # This attribute is defined by the AIPerfBaseModel class.
        if not hasattr(model, "_exclude_if_none_fields"):
            model._exclude_if_none_fields = set()
        model._exclude_if_none_fields.update(set(field_names))
        return model

    return decorator


def exclude_fields(*field_names: str):
    """Decorator to set the _exclude_fields class attribute to the set of
    field names that should be unconditionally excluded from serialization.
    """

    def decorator(model: type[AIPerfBaseModelT]) -> type[AIPerfBaseModelT]:
        # This attribute is defined by the AIPerfBaseModel class.
        if not hasattr(model, "_exclude_fields"):
            model._exclude_fields = set()
        model._exclude_fields.update(set(field_names))
        return model

    return decorator


class AIPerfBaseModel(BaseModel):
    """Base model for all AIPerf Pydantic models. This class is configured to allow
    arbitrary types to be used as fields as to allow for more flexible model definitions
    by end users without breaking the existing code.

    The @exclude_if_none decorator can be used to specify which fields should be
    excluded from the serialized model if they are None. The @exclude_fields decorator
    can be used to unconditionally exclude specific fields from serialization. These
    are workarounds for the fact that pydantic does not support specifying exclude_none
    on a per-field basis.
    """

    _exclude_if_none_fields: ClassVar[set[str]] = set()
    """Set of field names that should be excluded from the serialized model if they
    are None. This is set by the @exclude_if_none decorator.
    """

    _exclude_fields: ClassVar[set[str]] = set()
    """Set of field names that should be unconditionally excluded from the serialized
    model. This is set by the @exclude_fields decorator.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_serializer
    def _serialize_model(self) -> dict[str, Any]:
        """Serialize the model to a dictionary.

        This method overrides the default serializer to exclude fields that were marked
        with the @exclude_fields decorator, or fields with a value of None that were
        marked with the @exclude_if_none decorator.
        """
        return {
            k: v
            for k, v in self
            if k not in self._exclude_fields
            and not (k in self._exclude_if_none_fields and v is None)
        }
