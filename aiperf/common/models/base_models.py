# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self

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


def explicitly_set_fields(*field_names: str):
    """Decorator to set the _explicitly_set_fields class attribute to the set of
    field names that should be included in the serialized model, even when exclude_unset is True.
    """

    def decorator(model: type[AIPerfBaseModelT]) -> type[AIPerfBaseModelT]:
        # This attribute is defined by the AIPerfBaseModel class.
        if not hasattr(model, "_explicitly_set_fields"):
            model._explicitly_set_fields = set()
        model._explicitly_set_fields.update(set(field_names))
        return model

    return decorator


class AIPerfBaseModel(BaseModel):
    """Base model for all AIPerf Pydantic models. This class is configured to allow
    arbitrary types to be used as fields as to allow for more flexible model definitions
    by end users without breaking the existing code.

    The @exclude_if_none decorator can also be used to specify which fields
    should be excluded from the serialized model if they are None. This is a workaround
    for the fact that pydantic does not support specifying exclude_none on a per-field basis.
    """

    _exclude_if_none_fields: ClassVar[set[str]] = set()
    """Set of field names that should be excluded from the serialized model if they
    are None. This is set by the @exclude_if_none decorator.
    """

    _explicitly_set_fields: ClassVar[set[str]] = set()
    """Set of field names that should be included in the serialized model, even when exclude_unset is True.
    This is set by the @explicitly_set_fields decorator.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _apply_explicitly_set_fields(self) -> Self:
        """Apply the explicitly set fields to the model. This is used to ensure that the explicitly set fields
        are set to avoid losing them when using exclude_unset."""
        self.model_fields_set.update(self._explicitly_set_fields)
        return self

    # @model_serializer
    # def _serialize_model(self) -> dict[str, Any]:
    #     """Serialize the model to a dictionary.

    #     This method overrides the default serializer to exclude fields that with a
    #     value of None and were marked with the @exclude_if_none decorator.
    #     """
    #     return {
    #         k: v
    #         for k, v in self
    #         if not (k in self._exclude_if_none_fields and v is None)
    #     }
