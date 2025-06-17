#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import random
from abc import ABC, abstractmethod
from typing import Any

from typing_extensions import Protocol

from aiperf.common.config import OutputTokenDefaults, UserConfig
from aiperf.common.enums import ModelSelectionStrategy
from aiperf.common.exceptions import AIPerfError
from aiperf.common.models.data_models import DataRow, GenericDataset
from aiperf.common.tokenizer import Tokenizer
from aiperf.common.utils import sample_bounded_normal


class RequestConverterProtocol(Protocol):
    def check_config(self) -> None: ...

    def convert(self, generic_dataset: GenericDataset) -> dict[Any, Any]: ...


class BaseRequestConverter(ABC):
    def __init__(self, config: UserConfig, tokenizer: Tokenizer | None = None):
        self.config = config
        self.tokenizer = tokenizer or Tokenizer()

    """
    Base class for all converters that take generic JSON payloads
    and convert them to endpoint-specific payloads.
    """

    @abstractmethod
    def check_config(self) -> None:
        """
        Check whether the provided configuration is valid for this converter.

        Throws a AIPerfError if the configuration is invalid.
        """
        ...

    @abstractmethod
    def convert(self, generic_dataset: GenericDataset) -> dict[Any, Any]:
        """
        Construct a request body using the endpoint specific request format.
        """
        ...

    # TODO: Multimodal support using the model_selection_strategy MODALITY_AWARE
    def _select_model_name(self, index: int, row: DataRow) -> str:
        if (
            self.config.endpoint.model_selection_strategy
            == ModelSelectionStrategy.ROUND_ROBIN
        ):
            return self.config.model_names[index % len(self.config.model_names)]
        elif (
            self.config.endpoint.model_selection_strategy
            == ModelSelectionStrategy.RANDOM
        ):
            return random.choice(self.config.model_names)
        else:
            raise AIPerfError(
                f"Model selection strategy '{self.config.endpoint.model_selection_strategy}' is unsupported"
            )

    def _get_max_tokens(self, optional_data: dict[Any, Any]) -> int | None:
        """
        Return the `max_tokens` value to be added in the payload.
        If `max_tokens` is present in `optional_data`, that value is used.
        Otherwise, `max_tokens` is sampled from a bounded normal
        distribution with a minimum value of 1.
        """
        if "max_tokens" in optional_data:
            return optional_data["max_tokens"]
        elif self.config.input.output_tokens.mean is not None:
            return int(
                sample_bounded_normal(
                    mean=self.config.input.output_tokens.mean,
                    stddev=self.config.input.output_tokens.stddev,
                    lower=1,  # output token must be >= 1
                )
            )
        return OutputTokenDefaults.MEAN

    def _add_request_params(
        self,
        payload: dict[Any, Any],
        optional_data: dict[Any, Any],
    ) -> None:
        if self.config.input.extra:
            for key, value in self.config.input.extra.items():
                payload[key] = value

    def _add_payload_optional_data(self, payload: dict[Any, Any], row: DataRow) -> None:
        for key, value in row.optional_data.items():
            payload[key] = value

    def _add_payload_metadata(self, record: dict[str, Any], row: DataRow) -> None:
        for key, value in row.payload_metadata.items():
            record[key] = [value]

    def _finalize_payload(
        self,
        payload: dict[Any, Any],
        row: DataRow,
    ) -> dict[str, Any]:
        self._add_request_params(payload, row.optional_data)
        self._add_payload_optional_data(payload, row)
        record: dict[str, Any] = {"payload": [payload]}
        self._add_payload_metadata(record, row)

        return record
