#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Any

from aiperf.common.config._defaults import EndPointDefaults as EndPointDefaults
from aiperf.common.config._user import UserConfig as UserConfig
from aiperf.common.enums import EndpointType as EndpointType
from aiperf.common.enums import Modality as Modality
from aiperf.common.enums import ModelSelectionStrategy as ModelSelectionStrategy
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel

class ModelInfo(AIPerfBaseModel):
    name: str
    version: str | None
    modality: Modality

class ModelListInfo(AIPerfBaseModel):
    models: list[ModelInfo]
    model_selection_strategy: ModelSelectionStrategy
    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> ModelListInfo: ...

class EndpointInfo(AIPerfBaseModel):
    type: EndpointType
    base_url: str | None
    custom_endpoint: str | None
    streaming: bool
    headers: dict[str, str] | None
    api_key: str | None
    ssl_options: dict[str, Any] | None
    timeout_seconds: float
    extra: dict[str, Any] | None
    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> EndpointInfo: ...

class ModelEndpointInfo(AIPerfBaseModel):
    models: ModelListInfo
    endpoint: EndpointInfo
    @classmethod
    def from_user_config(cls, user_config: UserConfig) -> ModelEndpointInfo: ...
    @property
    def url(self) -> str: ...
    @property
    def primary_model(self) -> ModelInfo: ...
    @property
    def primary_model_name(self) -> str: ...
