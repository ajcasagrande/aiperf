# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tokenizer service for handling different model tokenizers."""

import logging
from typing import Any

from transformers import AutoTokenizer
from transformers.tokenization_utils import PreTrainedTokenizer

from .utils import supports_kwarg

logger = logging.getLogger(__name__)


class TokenizerService:
    """Service for managing tokenizers for different models."""

    def __init__(self):
        self._tokenizers: dict[str, PreTrainedTokenizer] = {}
        self._tokenizer_encode_opts: dict[str, dict[str, Any]] = {}
        self._tokenizer_decode_opts: dict[str, dict[str, Any]] = {}

    def load_tokenizers(self, model_names: list[str]) -> None:
        """Pre-load tokenizers for one or more models.

        Args:
            model_names: List of model names to load tokenizers for
        """
        for model_name in model_names:
            try:
                logger.info("Pre-loading tokenizer for model: %s", model_name)
                self._tokenizers[model_name] = AutoTokenizer.from_pretrained(
                    model_name, trust_remote_code=True
                )
                self._tokenizer_encode_opts[model_name] = {
                    "add_special_tokens": False,
                }
                self._tokenizer_decode_opts[model_name] = {
                    "skip_special_tokens": True,
                }

                if supports_kwarg(
                    self._tokenizers[model_name], "encode", "allow_special_tokens"
                ):
                    # If the tokenizer encode method supports allow_special_tokens
                    # then we override the normal 'add_special_tokens' parameter
                    # with 'allow_special_tokens' to match the behavior of the
                    # current tokenizer. (such as Kimi)
                    self._tokenizer_encode_opts[model_name] = {
                        "allow_special_tokens": False,
                    }
            except Exception as e:
                logger.exception("Failed to load tokenizer for %s: %s", model_name, e)

    def get_tokenizer(self, model_name: str) -> PreTrainedTokenizer:
        """Get or create a tokenizer for the specified model."""
        if model_name not in self._tokenizers:
            raise ValueError(f"No tokenizer loaded for {model_name}")

        return self._tokenizers[model_name]

    def tokenize(self, text: str, model_name: str) -> list[str]:
        """Tokenize text using the specified model's tokenizer."""
        tokenizer = self.get_tokenizer(model_name)

        # Encode and decode to get actual tokens as they would appear
        token_ids = tokenizer.encode(text, **self._tokenizer_encode_opts[model_name])
        tokens = []

        for token_id in token_ids:
            token_text = tokenizer.decode(
                [token_id], **self._tokenizer_decode_opts[model_name]
            )
            tokens.append(token_text)

        return tokens

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count the number of tokens in the text for the specified model."""
        tokenizer = self.get_tokenizer(model_name)
        return len(tokenizer.encode(text, **self._tokenizer_encode_opts[model_name]))


# Global tokenizer service instance
tokenizer_service = TokenizerService()
