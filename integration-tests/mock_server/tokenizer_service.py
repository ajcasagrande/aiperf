# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tokenizer service for handling different model tokenizers."""

import logging

from aiperf.common.config.prompt_config import PromptConfig
from aiperf.common.tokenizer import Tokenizer
from aiperf.dataset.generator import PromptGenerator

logger = logging.getLogger(__name__)


class TokenizerService:
    """Service for managing tokenizers for different models."""

    def __init__(self):
        self._tokenizers: dict[str, Tokenizer] = {}
        self._prompt_generators: dict[str, PromptGenerator] = {}
        self._datasets: dict[str, list[str]] = {}
        self._fallback_model_name: str | None = None

    def load_tokenizers(self, model_names: list[str]) -> None:
        """Pre-load tokenizers for one or more models.

        Args:
            model_names: List of model names to load tokenizers for
        """
        for model_name in model_names:
            try:
                logger.info(f"Pre-loading tokenizer for model: {model_name}")
                tokenizer = Tokenizer.from_pretrained(
                    model_name, trust_remote_code=True
                )
                self._tokenizers[model_name] = tokenizer
                logger.info(f"Pre-loading prompt generator for model: {model_name}")
                self._prompt_generators[model_name] = PromptGenerator(
                    PromptConfig(),
                    tokenizer,
                )
                tokens = self._prompt_generators[model_name].generate(
                    mean=1000,
                    stddev=0.0,
                )
                logger.info(f"Generated {len(tokens)} tokens for model: {model_name}")
                self._datasets[model_name] = [
                    tokenizer.decode([token_id]) for token_id in tokens
                ]

            except Exception as e:
                logger.exception(f"Failed to load tokenizer for {model_name}: {e}")

    def get_tokenizer(self, model_name: str) -> Tokenizer:
        """Get or create a tokenizer for the specified model."""
        if model_name not in self._tokenizers:
            raise ValueError(f"No tokenizer loaded for {model_name}")

        return self._tokenizers[model_name]

    def get_dataset(self, model_name: str) -> list[str]:
        """Get the dataset for the specified model."""
        if model_name not in self._datasets:
            raise ValueError(f"No dataset loaded for {model_name}")

        return self._datasets[model_name]

    def generate_response(self, prompt: str, model_name: str) -> list[str]:
        """Generate a response for the specified model."""
        if model_name not in self._datasets:
            if self._fallback_model_name not in self._datasets:
                raise ValueError(
                    f"No dataset loaded for {model_name} or {self._fallback_model_name}"
                )
            model_name = self._fallback_model_name

        token_count = self.estimate_token_count(prompt)
        response = self._datasets[model_name][:token_count]
        while len(response) < token_count:
            response += self._datasets[model_name][: token_count - len(response)]
        return response

    def tokenize(self, text: str, model_name: str) -> list[str]:
        """Tokenize text using the specified model's tokenizer."""
        tokenizer = self.get_tokenizer(model_name)

        # Encode and decode to get actual tokens as they would appear
        token_ids = tokenizer.encode(text)
        tokens = []

        for token_id in token_ids:
            token_text = tokenizer.decode([token_id])
            tokens.append(token_text)

        return tokens

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count the number of tokens in the text for the specified model."""
        tokenizer = self.get_tokenizer(model_name)
        return len(tokenizer.encode(text))

    def estimate_token_count(self, text: str) -> int:
        """Estimate the number of tokens in the text.

        This is a rough estimate based on the average token length of 4 characters.
        """
        return len(text) // 4


# Global tokenizer service instance
tokenizer_service = TokenizerService()
